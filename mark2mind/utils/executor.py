from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os
import atexit
import threading

# Lazily-initialized singleton
_executor_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None

def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                max_workers = int(os.getenv("MARK2MIND_MAX_WORKERS", "20"))
                _executor = ThreadPoolExecutor(max_workers=max_workers)
                atexit.register(_shutdown_executor)
    return _executor

def _shutdown_executor():
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True, cancel_futures=False)
        _executor = None
