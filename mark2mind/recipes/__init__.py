from __future__ import annotations
from importlib.resources import files as _pkg_files
from pathlib import Path
import os
import shutil
from typing import Dict, List

# -----------------------------
# Canonical recipe registry
# -----------------------------
# Keep these in sync with files in mark2mind/recipes/
CANONICAL: Dict[str, str] = {
    "mindmap_from_markdown": "mindmap_from_markdown.toml",
    "detailed_mindmap_from_markdown": "detailed_mindmap_from_markdown.toml",
    "qa_from_markdown": "qa_from_markdown.toml",

    # renamed "subtitles" -> "notes" (more general)
    "list_notes_in_dir": "list_notes_in_dir.toml",
    "merge_notes_from_manifest": "merge_notes_from_manifest.toml",

    # cleanup/refactor flows
    "reformat_markdown": "reformat_markdown.toml",
    "focus_markdown": "focus_markdown.toml",           # de-jargon / keep technical core
    "outline_markdown": "outline_markdown.toml",       # bullets/outline
}

# -----------------------------
# Back-compat aliases
# -----------------------------
ALIASES: Dict[str, str] = {
    # old subtitles naming -> new notes naming
    "list_subtitles_in_dir": "list_notes_in_dir",
    "merge_subtitles_from_manifest": "merge_notes_from_manifest",

    # earlier naming experiments -> canonical
    "clarify_markdown": "focus_markdown",
    "bullets_from_markdown": "outline_markdown",
}

def _resolve_key(name: str) -> str:
    """Map alias -> canonical; pass through canonical as-is."""
    if name in CANONICAL:
        return name
    if name in ALIASES:
        return ALIASES[name]
    # Try tolerant fallback: if they passed a filename-ish key
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
    """Return canonical names (what we advertise)."""
    return sorted(CANONICAL.keys())

def _user_recipes_dir() -> Path:
    # Windows: %AppData%\mark2mind\recipes ; *nix/mac: ~/.mark2mind/recipes
    base = os.getenv("APPDATA") or os.path.expanduser("~/.mark2mind")
    return Path(base) / "mark2mind" / "recipes" if os.getenv("APPDATA") else Path(base) / "recipes"

def _copy_builtins_to_user_once() -> None:
    """On first run, copy packaged recipes into the user dir so users can edit them."""
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
            # best-effort; ignore copy errors
            pass
    sentinel.write_text("ok", encoding="utf-8")

def get_recipe_path(name: str) -> Path:
    """Return a Path to the recipe TOML (prefers user override; falls back to packaged)."""
    canon = _resolve_key(name)

    # Prefer user override (after seeding)
    _copy_builtins_to_user_once()
    user_p = _user_recipes_dir() / CANONICAL[canon]
    if user_p.exists():
        return user_p

    # Fallback to built-ins (works under pip and PyInstaller)
    p = _pkg_files(__package__) / CANONICAL[canon]
    return Path(p)
