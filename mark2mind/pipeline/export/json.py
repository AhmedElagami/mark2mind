from __future__ import annotations
from pathlib import Path
import json

class JSONExporter:
    def export_mindmap(self, final_tree: dict, out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(final_tree, indent=2, ensure_ascii=False), encoding="utf-8")
