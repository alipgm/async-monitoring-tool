import asyncio
import aiohttp
import time
import json
from asyncio import subprocess
import logging

# --- App Configuration ---
URLS_TO_CHECK = [
    "https://www.python.org",
    "https://www.google.com",
    "https://www.github.com",
    "http://httpbin.org/delay/5",
    "https://invalid-url-for-testing.xyz",
]
# FIX 2: Replaced Linux commands with Windows-compatible ones
COMMANDS_TO_RUN = {
    "ip_config": "ipconfig",
    "task_list": "tasklist | find \"python.exe\"", # Example: find running python processes
    "directory_listing": "dir C:\\Users"
}

# --- Shared Resources & Sync Primitives ---
URL_SEMAPHORE = asyncio.Semaphore(3)
RESULTS_LOCK = asyncio.Lock()
REPORTER_CONDITION = asyncio.Condition()
SHUTDOWN_EVENT = asyncio.Event()
shared_results = []

# --- Setup Logging ---
def setup_logging():
    """Configures the logging system."""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # FIX 1: Add encoding='utf-8' to handlers to prevent UnicodeEncodeError
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.encoding = 'utf-8' # Explicitly set encoding for console

    # For the file handler, this is crucial
    file_handler = logging.FileHandler('monitoring.log', mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Clear existing handlers to avoid duplicates
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


logger = logging.getLogger(__name__)

# --- Coroutines (No changes needed here) ---
async def fetch_url_status(session: aiohttp.ClientSession, url: str):
    """Fetches a URL's status using aiohttp, limited by a semaphore."""
    async with URL_SEMAPHORE:
        logger.debug(f"Starting to check URL: {url}...")
        try:
            async with session.get(url, timeout=4.0) as response:
                logger.info(f"URL Check Success: {url} - Status: {response.status}")
                return {"type": "url", "source": url, "status": response.status, "success": True}
        except Exception as e:
            logger.warning(f"URL Check Failed: {url} - Error: {e}")
            return {"type": "url", "source": url, "error": str(e), "success": False}

async def run_system_command(command_name: str, command: str):
    """Runs a shell command using asyncio.subprocess."""
    logger.debug(f"Starting to run command: '{command_name}'...")
    try:
        process = await asyncio.create_subprocess_shell(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            logger.info(f"Command '{command_name}' executed successfully.")
            return {"type": "command", "source": command_name, "output": stdout.decode(errors='ignore').strip(), "success": True}
        else:
            logger.error(f"Command '{command_name}' failed with error: {stderr.decode(errors='ignore').strip()}")
            return {"type": "command", "source": command_name, "error": stderr.decode(errors='ignore').strip(), "success": False}
    except Exception as e:
        logger.critical(f"Critical error running command '{command_name}': {e}")
        return {"type": "command", "source": command_name, "error": str(e), "success": False}

async def reporter():
    """A background task that waits for new results and processes them."""
    logger.info("[Reporter] Started. Waiting for results...")
    while not SHUTDOWN_EVENT.is_set():
        async with REPORTER_CONDITION:
            await REPORTER_CONDITION.wait()
            async with RESULTS_LOCK:
                if shared_results:
                    logger.info(f"[Reporter] Processing {len(shared_results)} new results.")
                    while shared_results:
                        result = shared_results.pop(0)
                        logger.debug(f"[Reporter] Got result: {json.dumps(result)}")
    logger.info("[Reporter] Shutting down.")

async def main():
    """Main function to orchestrate all tasks."""
    setup_logging()

    start_time = time.time()
    # FIX 1: Removed emojis from log messages
    logger.info("Starting Advanced Concurrent Monitoring Tool...")

    reporter_task = asyncio.create_task(reporter())

    async with aiohttp.ClientSession() as session:
        url_tasks = [asyncio.create_task(fetch_url_status(session, url)) for url in URLS_TO_CHECK]
        command_tasks = [asyncio.create_task(run_system_command(name, cmd)) for name, cmd in COMMANDS_TO_RUN.items()]
        all_tasks = url_tasks + command_tasks
        logger.info(f"Total tasks created: {len(all_tasks)}")

        for future in asyncio.as_completed(all_tasks, timeout=10.0):
            try:
                result = await future
                async with RESULTS_LOCK:
                    shared_results.append(result)
                async with REPORTER_CONDITION:
                    REPORTER_CONDITION.notify()
            except asyncio.TimeoutError:
                logger.error("Overall timeout of 10s reached. Some tasks may not have completed.")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred in task processing: {e}")

        logger.info("Cancelling outstanding tasks...")
        cancelled_count = 0
        for task in all_tasks:
            if not task.done():
                task.cancel()
                cancelled_count += 1
        await asyncio.gather(*all_tasks, return_exceptions=True)
        logger.info(f"Cancelled {cancelled_count} tasks.")

    logger.info("Main workload finished. Shutting down reporter...")
    SHUTDOWN_EVENT.set()
    async with REPORTER_CONDITION:
        REPORTER_CONDITION.notify()
    await reporter_task

    end_time = time.time()
    logger.info(f"Monitoring finished in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.getLogger().info("Shutdown requested by user.")