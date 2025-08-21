# FILE: mark2mind/mark2mind/recipes/__init__.py
from __future__ import annotations
from importlib.resources import files as _pkg_files
from pathlib import Path
import os
import shutil
from typing import Dict, List

CANONICAL: Dict[str, str] = {
    "mindmap_from_markdown": "mindmap_from_markdown.toml",
    "detailed_mindmap_from_markdown": "detailed_mindmap_from_markdown.toml",
    "qa_from_markdown": "qa_from_markdown.toml",
    "list_notes_in_dir": "list_notes_in_dir.toml",
    "merge_notes_from_manifest": "merge_notes_from_manifest.toml",
    "reformat_markdown": "reformat_markdown.toml",
    "focus_markdown": "focus_markdown.toml",
    "outline_markdown": "outline_markdown.toml",
    # NEW:
    "mindmap_from_qa": "mindmap_from_qa.toml",
}

ALIASES: Dict[str, str] = {
    "list_subtitles_in_dir": "list_notes_in_dir",
    "merge_subtitles_from_manifest": "merge_notes_from_manifest",
    "clarify_markdown": "focus_markdown",
    "bullets_from_markdown": "outline_markdown",
}

def _resolve_key(name: str) -> str:
    if name in CANONICAL:
        return name
    if name in ALIASES:
        return ALIASES[name]
    stem = name.replace(".toml", "")
    if stem in CANONICAL:
        return stem
    if stem in ALIASES:
        return ALIASES[stem]
    raise SystemExit(
        f"Unknown recipe '{name}'. Try one of: {', '.join(sorted(CANONICAL.keys()))}"
        f" (aliases: {', '.join(sorted(ALIASES.keys()))})"
    )

def get_recipe_names() -> List[str]:
    return sorted(CANONICAL.keys())

def _user_recipes_dir() -> Path:
    base = os.getenv("APPDATA") or os.path.expanduser("~/.mark2mind")
    return Path(base) / "mark2mind" / "recipes" if os.getenv("APPDATA") else Path(base) / "recipes"

def _copy_builtins_to_user_once() -> None:
    target = _user_recipes_dir()
    target.mkdir(parents=True, exist_ok=True)
    sentinel = target / ".installed"
    if sentinel.exists():
        return
    pkg_root = _pkg_files(__package__)
    for filename in CANONICAL.values():
        src = pkg_root / filename
        dst = target / filename
        try:
            with src.open("rb") as fsrc, dst.open("wb") as fdst:
                shutil.copyfileobj(fsrc, fdst)
        except Exception:
            pass
    sentinel.write_text("ok", encoding="utf-8")

def get_recipe_path(name: str) -> Path:
    canon = _resolve_key(name)
    _copy_builtins_to_user_once()
    user_p = _user_recipes_dir() / CANONICAL[canon]
    if user_p.exists():
        return user_p
    p = _pkg_files(__package__) / CANONICAL[canon]
    return Path(p)
