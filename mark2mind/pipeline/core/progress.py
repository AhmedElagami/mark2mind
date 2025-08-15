from __future__ import annotations
from typing import Any, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn, TimeElapsedColumn, TimeRemainingColumn

class ProgressReporter:
    def start(self, description: str, total: Optional[int] = None) -> Any: ...
    def advance(self, task: Any, step: int = 1): ...
    def finish(self, task: Any): ...
    def close(self): ...

class RichProgressReporter(ProgressReporter):
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
            console=self.console,
        )
        self._started = False

    def __enter__(self): 
        self.progress.__enter__(); self._started = True; return self

    def __exit__(self, exc_type, exc, tb):
        self.progress.__exit__(exc_type, exc, tb); self._started = False

    def start(self, description: str, total: Optional[int] = None):
        return self.progress.add_task(description, total=total)

    def advance(self, task: Any, step: int = 1):
        self.progress.advance(task, step)

    def finish(self, task: Any):
        self.progress.update(task, completed=self.progress.tasks[task].total)

    def close(self):
        if self._started:
            self.progress.__exit__(None, None, None)
            self._started = False

class NoopProgressReporter(ProgressReporter):
    def start(self, description: str, total: Optional[int] = None) -> int: return 0
    def advance(self, task: Any, step: int = 1): pass
    def finish(self, task: Any): pass
    def close(self): pass
