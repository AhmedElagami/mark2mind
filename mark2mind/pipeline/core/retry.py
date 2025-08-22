from __future__ import annotations
import time, random, threading
from typing import Callable, Any

class Retryer:
    def __init__(self, max_retries: int = 4, min_delay_sec: float = 0.15):
        self.max_retries = max_retries
        self.min_delay_sec = min_delay_sec
        self._last_call_ts = 0.0
        self._lock = threading.Lock()

    def _rate_limit_pause(self):
        # Protect shared timestamp across threads
        with self._lock:
            now = time.time()
            dt = now - self._last_call_ts
            sleep_for = self.min_delay_sec - dt + random.uniform(0, 0.05) if dt < self.min_delay_sec else 0.0
            # Reserve slot now so other threads see the updated timestamp
            self._last_call_ts = time.time()
        if sleep_for > 0:
            time.sleep(sleep_for)

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit_pause()
                return fn(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                print(f"[retry] attempt {attempt} failed: {type(e).__name__}: {e}")
                backoff = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.25)
                time.sleep(backoff)
