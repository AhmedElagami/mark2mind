from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json

SCHEMA_VERSION = "v1"

class ArtifactStore:
    """
    Simple FS-backed artifact store under debug/ and output/ roots.
    """

    def __init__(self, debug_dir: Path, output_dir: Path, file_id: str):
        self.debug_dir = (debug_dir / file_id).resolve()
        self.output_dir = output_dir.resolve()
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _wrap(self, obj: Any, kind: str) -> Any:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
            "file_id": self.debug_dir.name,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "payload": obj,
        }

    def save_debug(self, name: str, obj: Any):
        p = self.debug_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self._wrap(obj, "debug"), indent=2, ensure_ascii=False), encoding="utf-8")

    def save_output_json(self, name: str, obj: Any):
        p = self.output_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_text(self, path_rel: str, text: str):
        p = self.output_dir / path_rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def exists(self, name: str) -> bool:
        return (self.debug_dir / name).exists()

    def load_debug(self, name: str) -> Optional[Any]:
        p = self.debug_dir / name
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw.get("payload")
