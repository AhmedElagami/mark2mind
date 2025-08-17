from __future__ import annotations
from importlib.resources import files
from pathlib import Path
from typing import Dict, List

# Registry of recipe -> toml filename (kept simple & deterministic)
RECIPE_INDEX: Dict[str, str] = {
    "list_subtitles_in_dir": "list_subtitles_in_dir.toml",
    "merge_subtitles_from_manifest": "merge_subtitles_from_manifest.toml",
    "reformat_markdown": "reformat_markdown.toml",
    "clarify_markdown": "clarify_markdown.toml",
    "mindmap_from_markdown": "mindmap_from_markdown.toml",
    "detailed_mindmap_from_markdown": "detailed_mindmap_from_markdown.toml",
    "qa_from_markdown": "qa_from_markdown.toml",
}

def get_recipe_names() -> List[str]:
    return sorted(RECIPE_INDEX.keys())

def get_recipe_path(name: str) -> Path:
    if name not in RECIPE_INDEX:
        raise SystemExit(f"Unknown recipe '{name}'. Try one of: {', '.join(get_recipe_names())}")
    pkg_root = files(__package__)
    p = pkg_root / RECIPE_INDEX[name]
    return Path(p)
