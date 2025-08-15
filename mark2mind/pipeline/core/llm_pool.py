from __future__ import annotations
import threading
from typing import Optional, Callable, Dict, Any

class LLMFactoryPool:
    """
    One client per thread. If factory is None, stages reuse provided chains' internal clients.
    """
    def __init__(self, factory: Optional[Callable[[], Any]] = None):
        self.factory = factory
        self._thread_local = threading.local()

    def get(self):
        if getattr(self._thread_local, "llm", None) is None:
            self._thread_local.llm = self.factory() if self.factory else None
        return self._thread_local.llm
