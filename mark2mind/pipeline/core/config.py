from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import List, Optional

@dataclass
class RunConfig:
    file_id: str
    input_file: Path
    debug_dir: Path = Path("debug")
    output_dir: Path = Path("output")
    steps: List[str] = field(default_factory=lambda: ["chunk", "tree", "cluster", "merge", "refine", "map"])
    run_id: str = "manual"
    force: bool = False

    # performance / retries
    min_delay_sec: float = float(os.getenv("MARK2MIND_MIN_DELAY_SEC", "0.15"))
    max_retries: int = int(os.getenv("MARK2MIND_MAX_RETRIES", "4"))
    executor_max_workers: Optional[int] = None  # None => default ThreadPoolExecutor behavior
    map_batch_override: Optional[int] = None    # from MARK2MIND_MAP_BATCH if set

    def __post_init__(self):
        env_map = os.getenv("MARK2MIND_MAP_BATCH", "").strip().lower()
        if env_map.isdigit():
            self.map_batch_override = int(env_map)
