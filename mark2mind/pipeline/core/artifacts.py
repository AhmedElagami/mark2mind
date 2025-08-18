from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json


SCHEMA_VERSION = "v2-min"


class ArtifactStore:
    """
    Workspace-aware artifact store.

    WHY:
    - All outputs are auto-named under <output_root>/<run_name>/...
    - All debug are under <debug_root>/<run_name>/...
    - NO user-provided filenames needed (“Option B” auto-naming).
    """

    def __init__(self, debug_root: Path, output_root: Path, run_name: str, enable_debug: bool):
        self.run_name = run_name

        self.debug_root = Path(debug_root).resolve()
        self.output_root = Path(output_root).resolve()

        self.debug_dir = (self.debug_root / run_name).resolve()
        self.workspace_dir = (self.output_root / run_name).resolve()

        # Only create debug dir if enabled
        if enable_debug:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    # ----- helpers ------------------------------------------------------------
    def _wrap(self, obj: Any, kind: str) -> Any:
        return {
            "schema_version": SCHEMA_VERSION,
            "kind": kind,
            "run_name": self.run_name,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "payload": obj,
        }

    # ----- debug artifacts ----------------------------------------------------
    def save_debug(self, name: str, obj: Any):
        p = self.debug_dir / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self._wrap(obj, "debug"), indent=2, ensure_ascii=False), encoding="utf-8")

    def exists(self, name: str) -> bool:
        return (self.debug_dir / name).exists()

    def load_debug(self, name: str) -> Optional[Any]:
        p = self.debug_dir / name
        if not p.exists():
            return None
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw.get("payload")

    # ----- final outputs (auto-named) ----------------------------------------
    def write_text(self, rel_path: str, text: str):
        """
        Writes under workspace dir, keeping path relative.

        Example:
          write_text("mindmap.markmap.md", "...")
          write_text("subs/file_list.txt", "...")
        """
        p = self.workspace_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def save_output_json(self, rel_path: str, obj: Any):
        p = self.workspace_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

    # Resolve path inside workspace (handy for subtitles manifest)
    def resolve_workspace_path(self, rel_path: str) -> Path:
        return (self.workspace_dir / rel_path).resolve()
