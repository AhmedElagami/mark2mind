from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class QAPair:
    element_id: str
    question: str
    answer: str

@dataclass
class Block:
    element_id: str
    type: str
    text: str = ""
    markdown: str = ""
    heading_path: List[str] = field(default_factory=list)
    token_count: int = 0
    qa_pairs: List[Dict] = field(default_factory=list)

@dataclass
class Chunk:
    blocks: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
