from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

class ExecutorProvider:
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers

    def get(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(max_workers=self.max_workers)
