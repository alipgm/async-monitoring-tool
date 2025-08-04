# 🚀 Advanced Async Monitoring Tool in Python

This project is a powerful, concurrent web and system monitoring tool built entirely with Python's `asyncio` library. It serves as a practical demonstration of advanced asynchronous programming concepts and is designed to be a strong portfolio piece.

## ✨ Features

- **Concurrent URL Checking**: Monitors multiple websites simultaneously using `aiohttp`.
- **Concurrent System Commands**: Executes local system commands (like `df -h` or `free -h`) in parallel using `asyncio.subprocess`.
- **Concurrency Limiting**: Uses an `asyncio.Semaphore` to prevent overwhelming the network with too many requests.
- **Real-time Reporting**: Processes results as soon as they are available using `asyncio.as_completed`.
- **Graceful Shutdown & Task Cancellation**: Handles timeouts gracefully and cancels long-running or outstanding tasks.
- **Thread-Safe Operations**: Protects shared data structures (`list` of results) with `asyncio.Lock`.
- **Producer-Consumer Pattern**: Implements a sophisticated producer-consumer pattern using `asyncio.Condition` to notify a reporter task of new results.
- **Coordinated Shutdown**: Uses `asyncio.Event` to signal a clean shutdown to background tasks.

## 🛠️ How It Works & Concepts Demonstrated

This project showcases mastery of the following `asyncio` concepts:

| Concept | Implementation in `main.py` |
| :--- | :--- |
| **`coroutines`** | All `async def` functions, like `fetch_url_status` and `run_system_command`, are coroutines. |
| **`aiohttp`** | Used in `fetch_url_status` for making non-blocking, asynchronous HTTP requests. |
| **`event-loop`** | Implicitly managed by `asyncio.run(main())`, which orchestrates all tasks. |
| **`Semaphore`** | `URL_SEMAPHORE` limits concurrent URL checks to 3, preventing server overload. |
| **`Lock`** | `RESULTS_LOCK` ensures that only one task at a time can write to the `shared_results` list. |
| **`subprocess`** | `asyncio.create_subprocess_shell` is used in `run_system_command` to execute shell commands asynchronously. |
| **`as_completed`** | The main loop uses `for future in asyncio.as_completed(...)` to process tasks as they finish, providing real-time feedback. |
| **`cancel`** | In the cleanup phase, `task.cancel()` is called on any tasks that haven't finished after the main workload. |
| **`Condition`** | `REPORTER_CONDITION` allows the `reporter` task to sleep (`await condition.wait()`) until another task adds a result and calls `condition.notify()`. |
| **`Event`** | `SHUTDOWN_EVENT` is used to signal the `reporter` task to exit its loop and terminate gracefully. |
| **`gather`** | `asyncio.gather(*all_tasks, ...)` is used after the cancellation loop to wait for all tasks (including the cancelled ones) to finalize. |
| **`wait`** | (Alternative) While not used in the final version, `asyncio.wait()` could be an alternative to `as_completed`. `as_completed` is better here because we want to process results one-by-one. `wait` would block until all tasks (or the first one) are complete, which is less interactive. |

## ⚙️ How to Run

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd async-monitoring-tool
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the script:**
    ```bash
    python main.py
    ```

You will see the tool starting, creating tasks, and the reporter printing results as they become available.