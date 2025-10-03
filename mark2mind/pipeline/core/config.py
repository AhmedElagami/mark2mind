from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import List, Optional

from mark2mind.config_schema import AppConfig


@dataclass
class RunConfig:
    """
    v2-min runtime config (resolved from AppConfig).

    WHAT changed:
    - file_id -> run_name
    - input file/dir inferred as mode; input_path retained
    - outputs/debug write under <output_dir>/<run_name>/...
    """
    run_name: str
    input_path: Path
    is_dir_mode: bool
    markmap_input_path: Optional[Path] = None

    debug_root: Path = Path("debug")
    output_root: Path = Path("output")

    steps: List[str] = field(default_factory=lambda: ["chunk", "tree", "cluster", "merge", "refine", "map"])
    run_id: str = "manual"
    use_debug_io: bool = False
    app: Optional[AppConfig] = None

    # execution knobs
    min_delay_sec: float = float(os.getenv("MARK2MIND_MIN_DELAY_SEC", "0.15"))
    max_retries: int = int(os.getenv("MARK2MIND_MAX_RETRIES", "4"))
    executor_max_workers: Optional[int] = None
    map_batch_override: Optional[int] = None

    def __post_init__(self):
        env_map = os.getenv("MARK2MIND_MAP_BATCH", "").strip().lower()
        if env_map.isdigit():
            self.map_batch_override = int(env_map)

    @classmethod
    def from_app(cls, app: AppConfig):
        # Steps from preset if present (steps list wins otherwise handled in main)
        steps = app.pipeline.steps
        if app.pipeline.preset:
            preset_map = app.presets.named or {}
            steps = preset_map.get(app.pipeline.preset, steps)

        primary_input = app.io.input or app.io.qa_input or app.io.markmap_input
        if not primary_input:
            raise ValueError("RunConfig requires at least one input path")

        input_path = Path(primary_input)
        is_dir_mode = input_path.is_dir()
        markmap_input = Path(app.io.markmap_input) if app.io.markmap_input else None

        return cls(
            run_name=app.io.run_name or input_path.stem,
            input_path=input_path,
            is_dir_mode=is_dir_mode,
            markmap_input_path=markmap_input,
            debug_root=Path(app.io.debug_dir),
            output_root=Path(app.io.output_dir),
            steps=steps,
            use_debug_io=app.runtime.use_debug_io,
            min_delay_sec=app.runtime.min_delay_sec,
            max_retries=app.runtime.max_retries,
            executor_max_workers=app.runtime.executor_max_workers,
            app=app,
        )
