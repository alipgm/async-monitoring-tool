import asyncio
import aiohttp
import time
import json
from asyncio import subprocess

# --- App Configuration ---
URLS_TO_CHECK = [
    "https://www.python.org",
    "https://www.google.com",
    "https://www.github.com",
    "http://httpbin.org/delay/5",  # A slow endpoint to test timeouts
    "https://invalid-url-for-testing.xyz",
]
COMMANDS_TO_RUN = {
    "disk_usage": "df -h",      # for Linux/macOS
    "memory_info": "free -h",   # for Linux/macOS
    # "directory_list": "dir"   # for Windows
}

# --- Shared Resources & Sync Primitives ---
URL_SEMAPHORE = asyncio.Semaphore(3)      # Limit concurrent network requests to 3
RESULTS_LOCK = asyncio.Lock()             # Lock to safely append to shared_results
REPORTER_CONDITION = asyncio.Condition()  # Condition to notify reporter of new results
SHUTDOWN_EVENT = asyncio.Event()          # Event to signal shutdown to background tasks
shared_results = []                       # Shared list for storing results

# --- Coroutines ---
async def fetch_url_status(session: aiohttp.ClientSession, url: str):
    """Fetches a URL's status using aiohttp, limited by a semaphore."""
    async with URL_SEMAPHORE:
        print(f"Checking URL: {url}...")
        try:
            async with session.get(url, timeout=4.0) as response:
                return {"type": "url", "source": url, "status": response.status, "success": True}
        except Exception as e:
            return {"type": "url", "source": url, "error": str(e), "success": False}

async def run_system_command(command_name: str, command: str):
    """Runs a shell command using asyncio.subprocess."""
    print(f"Running command: '{command_name}'...")
    try:
        process = await asyncio.create_subprocess_shell(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            return {"type": "command", "source": command_name, "output": stdout.decode().strip(), "success": True}
        else:
            return {"type": "command", "source": command_name, "error": stderr.decode().strip(), "success": False}
    except Exception as e:
        return {"type": "command", "source": command_name, "error": str(e), "success": False}

async def reporter():
    """A background task that waits for new results and prints them."""
    print("[Reporter] Started. Waiting for results...")
    while not SHUTDOWN_EVENT.is_set():
        async with REPORTER_CONDITION:
            await REPORTER_CONDITION.wait() # Wait for a new result or shutdown signal
            async with RESULTS_LOCK:
                if shared_results:
                    print("\n--- [Reporter] New Results! ---")
                    while shared_results:
                        result = shared_results.pop(0)
                        print(json.dumps(result, indent=2))
                    print("--------------------------------\n")
    print("[Reporter] Shutting down.")

async def main():
    """Main function to orchestrate all tasks."""
    start_time = time.time()
    print("🚀 Starting Advanced Concurrent Monitoring Tool...")

    reporter_task = asyncio.create_task(reporter()) # Run the reporter task in the background

    async with aiohttp.ClientSession() as session:
        # --- Create and process tasks as they complete ---
        url_tasks = [asyncio.create_task(fetch_url_status(session, url)) for url in URLS_TO_CHECK]
        command_tasks = [asyncio.create_task(run_system_command(name, cmd)) for name, cmd in COMMANDS_TO_RUN.items()]
        all_tasks = url_tasks + command_tasks
        print(f"Total tasks created: {len(all_tasks)}")

        for future in asyncio.as_completed(all_tasks, timeout=10.0):
            try:
                result = await future
                async with RESULTS_LOCK:
                    shared_results.append(result) # Add result safely using the lock
                async with REPORTER_CONDITION:
                    REPORTER_CONDITION.notify() # Notify the reporter of the new result
            except asyncio.TimeoutError:
                print("\n🔥 A task took too long! Overall timeout reached.")
                break # Break from the as_completed loop
            except Exception as e:
                print(f"An unexpected error occurred in task processing: {e}")

        # --- Cancel any remaining tasks ---
        print("\nCancelling outstanding tasks...")
        cancelled_count = 0
        for task in all_tasks:
            if not task.done():
                task.cancel()
                cancelled_count += 1
        # Wait for all tasks to finish, including cancelled ones
        await asyncio.gather(*all_tasks, return_exceptions=True)
        print(f"Cancelled {cancelled_count} tasks.")

    # --- Finalize and Cleanup ---
    print("\n✅ Main workload finished. Shutting down reporter...")
    SHUTDOWN_EVENT.set() # Signal the reporter to shut down
    async with REPORTER_CONDITION:
        REPORTER_CONDITION.notify() # Notify reporter one last time to check the shutdown event
    await reporter_task # Wait for the reporter task to finish

    end_time = time.time()
    print(f"\n✨ Monitoring finished in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    try:
        asyncio.run(main()) # asyncio.run() manages the event loop
    except KeyboardInterrupt:
        print("\nShutdown requested by user.")