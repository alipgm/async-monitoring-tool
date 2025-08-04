import asyncio
import aiohttp
import time
import json
from asyncio import subprocess

# --- پیکربندی برنامه ---
# لیستی از وب‌سایت‌ها برای بررسی وضعیت
URLS_TO_CHECK = [
    "https://www.python.org",
    "https://www.google.com",
    "https://www.github.com",
    "http://httpbin.org/delay/5",  # این آدرس برای شبیه‌سازی کندی و تست Timeout است
    "https://invalid-url-for-testing.xyz",
]

# لیستی از دستورات سیستمی برای اجرا
# در ویندوز از 'dir' و در لینوکس/مک از 'ls -l' استفاده کنید
COMMANDS_TO_RUN = {
    "disk_usage": "df -h",  # for Linux/macOS
    "memory_info": "free -h", # for Linux/macOS
    # "directory_list": "dir" # for Windows
}

# --- منابع مشترک و ابزارهای همزمانی (Synchronization Primitives) ---

# Semaphore: برای محدود کردن تعداد درخواست‌های همزمان شبکه به 3 عدد
# این کار از ارسال درخواست‌های زیاد و بلاک شدن توسط سرور جلوگیری می‌کند
URL_SEMAPHORE = asyncio.Semaphore(3)

# Lock: برای محافظت از دسترسی همزمان به لیست نتایج
# وقتی یک تسک در حال نوشتن در این لیست است، بقیه باید منتظر بمانند
RESULTS_LOCK = asyncio.Lock()

# Condition: برای اطلاع‌رسانی به تسک گزارش‌دهنده (reporter) که نتیجه جدیدی اضافه شده است
# Reporter منتظر این Condition می‌ماند و با هر notify بیدار می‌شود
REPORTER_CONDITION = asyncio.Condition()

# Event: برای ارسال سیگنال خاموش شدن (Shutdown) به تسک‌های پس‌زمینه
SHUTDOWN_EVENT = asyncio.Event()

# لیست اشتراکی برای ذخیره نتایج
shared_results = []


# --- Coroutines (توابع async) ---

async def fetch_url_status(session: aiohttp.ClientSession, url: str):
    """
    (Coroutine) یک URL را با استفاده از aiohttp بررسی کرده و نتیجه را برمی‌گرداند.
    از Semaphore برای کنترل تعداد درخواست‌های همزمان استفاده می‌کند.
    """
    async with URL_SEMAPHORE:
        print(f"Checking URL: {url}...")
        try:
            async with session.get(url, timeout=4.0) as response:
                return {"type": "url", "source": url, "status": response.status, "success": True}
        except Exception as e:
            return {"type": "url", "source": url, "error": str(e), "success": False}


async def run_system_command(command_name: str, command: str):
    """
    (Coroutine) یک دستور سیستمی را با استفاده از asyncio.subprocess اجرا می‌کند.
    """
    print(f"Running command: '{command_name}'...")
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return {"type": "command", "source": command_name, "output": stdout.decode().strip(), "success": True}
        else:
            return {"type": "command", "source": command_name, "error": stderr.decode().strip(), "success": False}

    except Exception as e:
        return {"type": "command", "source": command_name, "error": str(e), "success": False}


async def reporter():
    """
    (Coroutine) یک تسک پس‌زمینه که منتظر نتایج جدید می‌ماند و آن‌ها را چاپ می‌کند.
    از Condition برای انتظار و از Event برای خاموش شدن استفاده می‌کند.
    """
    print("[Reporter] Started. Waiting for results...")
    while not SHUTDOWN_EVENT.is_set():
        async with REPORTER_CONDITION:
            # منتظر بمان تا یک نتیجه جدید اضافه شود یا سیگنال خاموش شدن صادر شود
            await REPORTER_CONDITION.wait()

            # وقتی بیدار شد، تمام نتایج جدید را پردازش کن
            async with RESULTS_LOCK:
                if shared_results:
                    print("\n--- [Reporter] New Results! ---")
                    while shared_results:
                        result = shared_results.pop(0)
                        print(json.dumps(result, indent=2))
                    print("--------------------------------\n")
    print("[Reporter] Shutting down.")


async def main():
    """
    تابع اصلی برنامه که تمام Coroutine‌ها را ارکستریت (Orchestrate) می‌کند.
    """
    start_time = time.time()
    print("🚀 Starting Advanced Concurrent Monitoring Tool...")

    # اجرای تسک گزارش‌دهنده در پس‌زمینه
    reporter_task = asyncio.create_task(reporter())

    async with aiohttp.ClientSession() as session:
        # --- ایجاد تسک‌ها ---
        url_tasks = [asyncio.create_task(fetch_url_status(session, url)) for url in URLS_TO_CHECK]
        command_tasks = [asyncio.create_task(run_system_command(name, cmd)) for name, cmd in COMMANDS_TO_RUN.items()]
        
        # --- استفاده از as_completed برای پردازش نتایج به محض آماده شدن ---
        # این الگو برای کارهایی که زمان اتمام نامشخصی دارند عالی است
        all_tasks = url_tasks + command_tasks
        print(f"Total tasks created: {len(all_tasks)}")

        for future in asyncio.as_completed(all_tasks, timeout=10.0):
            try:
                result = await future
                
                # استفاده از Lock و Condition برای افزودن نتیجه
                async with RESULTS_LOCK:
                    shared_results.append(result)
                
                # به تسک Reporter اطلاع بده که نتیجه جدیدی آماده است
                async with REPORTER_CONDITION:
                    REPORTER_CONDITION.notify()

            except asyncio.TimeoutError:
                print("\n🔥 A task took too long! Overall timeout reached.")
                break # از حلقه as_completed خارج شو
            except Exception as e:
                print(f"An unexpected error occurred in task processing: {e}")

        # --- لغو (Cancel) تسک‌های باقی‌مانده ---
        # پس از اتمام کار یا Timeout، تسک‌هایی که هنوز تمام نشده‌اند را لغو می‌کنیم
        print("\nCancelling outstanding tasks...")
        cancelled_count = 0
        for task in all_tasks:
            if not task.done():
                task.cancel()
                cancelled_count += 1
        
        # با استفاده از gather منتظر می‌مانیم تا تسک‌های لغو شده تمام شوند
        # return_exceptions=True از کرش کردن برنامه جلوگیری می‌کند
        await asyncio.gather(*all_tasks, return_exceptions=True)
        print(f"Cancelled {cancelled_count} tasks.")


    # --- اتمام کار و پاکسازی ---
    print("\n✅ Main workload finished. Shutting down reporter...")
    # به Reporter سیگنال خاموش شدن بده
    SHUTDOWN_EVENT.set()
    async with REPORTER_CONDITION:
        REPORTER_CONDITION.notify() # یک بار دیگر Reporter را بیدار کن تا Event را چک کند

    # منتظر بمان تا Reporter کارش تمام شود
    await reporter_task

    end_time = time.time()
    print(f"\n✨ Monitoring finished in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    try:
        # asyncio.run() حلقه رویداد (event-loop) را مدیریت می‌کند
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")