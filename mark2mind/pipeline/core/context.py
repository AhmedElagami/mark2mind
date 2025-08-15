from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class StageStats:
    name: str
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RunContext:
    # primary working data
    text: str = ""
    chunks: List[Dict] = field(default_factory=list)
    chunk_results: List[Dict] = field(default_factory=list)
    clustered: List[List[Dict]] = field(default_factory=list)
    cluster_trees: List[Dict] = field(default_factory=list)
    final_tree: Dict = field(default_factory=dict)

    # misc
    stats: List[StageStats] = field(default_factory=list)

    def add_stats(self, name: str, **details):
        self.stats.append(StageStats(name=name, details=details))
