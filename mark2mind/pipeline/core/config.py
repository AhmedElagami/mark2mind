from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import List, Optional
from mark2mind.config_schema import AppConfig

@dataclass
class RunConfig:
    file_id: str
    input_file: Path
    debug_dir: Path = Path("debug")
    output_dir: Path = Path("output")
    steps: List[str] = field(default_factory=lambda: ["chunk", "tree", "cluster", "merge", "refine", "map"])
    run_id: str = "manual"
    force: bool = False
    app: Optional[AppConfig] = None

    # performance / retries
    min_delay_sec: float = float(os.getenv("MARK2MIND_MIN_DELAY_SEC", "0.15"))
    max_retries: int = int(os.getenv("MARK2MIND_MAX_RETRIES", "4"))
    executor_max_workers: Optional[int] = None  # None => default ThreadPoolExecutor behavior
    map_batch_override: Optional[int] = None    # from MARK2MIND_MAP_BATCH if set

    def __post_init__(self):
        env_map = os.getenv("MARK2MIND_MAP_BATCH", "").strip().lower()
        if env_map.isdigit():
            self.map_batch_override = int(env_map)

    @classmethod
    def from_app(cls, app: AppConfig, *, file_id: Optional[str] = None, input_file: Optional[Path] = None):
        paths = app.paths
        steps = app.pipeline.steps
        if app.pipeline.preset:
            preset_name = app.pipeline.preset
            preset_map = app.presets.named or {}
            if preset_name in preset_map:
                steps = preset_map[preset_name]
        return cls(
            file_id=file_id or paths.file_id or "run",
            input_file=input_file or Path(paths.input_file or "input.md"),
            debug_dir=Path(paths.debug_dir),
            output_dir=Path(paths.output_dir),
            steps=steps,
            force=app.runtime.force,
            min_delay_sec=app.runtime.min_delay_sec,
            max_retries=app.runtime.max_retries,
            executor_max_workers=app.runtime.executor_max_workers,
            app=app,
        )
