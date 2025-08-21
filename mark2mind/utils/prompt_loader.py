from __future__ import annotations

from importlib.resources import files as _pkg_files
from pathlib import Path
import sys

BUILTIN_PROMPTS = {
    "chunk_tree":   "prompts/mindmap/mindmap_generator.txt",
    "merge_tree":   "prompts/mindmap/mindmap_merger.txt",
    "refine_tree":  "prompts/mindmap/mindmap_refiner.txt",
    "map_content":  "prompts/mindmap/content_mapper.txt",
    "map_content_qa":"prompts/mindmap/content_mapper_qa.txt",  # NEW
    "qa_generate":  "prompts/qa/generate_questions.txt",
    "qa_answer":    "prompts/qa/answer_questions.txt",
    "format_bullets":"prompts/format/format_bullets.txt",
    "reformat_text":"prompts/format/reformat_text.txt",
    "clean_for_map":"prompts/format/clean_for_map.txt",
}

_PROMPT_FILE_OVERRIDES: dict[str, str] = {}


def _warn(msg: str) -> None:
    print(f"⚠️ {msg}", file=sys.stderr)


def set_prompt_file_overrides(mapping: dict[str, str] | None) -> None:
    global _PROMPT_FILE_OVERRIDES
    _PROMPT_FILE_OVERRIDES = dict(mapping or {})


def _read_pkg_text(rel_path: str) -> str:
    # Load from package resources (works installed and frozen)
    p = _pkg_files("mark2mind").joinpath(rel_path)
    try:
        return p.read_text(encoding="utf-8-sig")
    except Exception as e:
        raise FileNotFoundError(f"Built-in prompt missing: {rel_path}") from e


def load_prompt(key: str) -> str:
    # 1) user override (external file path)
    ov_path = _PROMPT_FILE_OVERRIDES.get(key)
    if ov_path:
        p = Path(ov_path)
        if p.exists():
            return p.read_text(encoding="utf-8-sig")
        _warn(f"[prompts.files] path for key '{key}' not found: {ov_path} → falling back to built-in.")

    # 2) built-in prompt bundled in the package
    rel = BUILTIN_PROMPTS.get(key)
    if not rel:
        raise ValueError(
            f"No built-in prompt for key: '{key}'. "
            "Valid keys include: " + ", ".join(sorted(BUILTIN_PROMPTS.keys()))
        )
    return _read_pkg_text(rel)
