from __future__ import annotations
from pathlib import Path
import sys


# =============================================================================
# BUILT-IN DEFAULT PROMPTS (file paths relative to project root)
# =============================================================================

BUILTIN_PROMPTS = {
    # Mindmap flow
    "chunk_tree": "prompts/mindmap/mindmap_generator.txt",
    "merge_tree": "prompts/mindmap/mindmap_merger.txt",
    "refine_tree": "prompts/mindmap/mindmap_refiner.txt",
    "map_content": "prompts/mindmap/content_mapper.txt",
    # Q&A flow
    "qa_generate": "prompts/qa/generate_questions.txt",
    "qa_answer": "prompts/qa/answer_questions.txt",
    # Formatting
    "format_bullets": "prompts/format/format_bullets.txt",
    "reformat_text": "prompts/format/reformat_text.txt",
    "clean_for_map": "prompts/format/clean_for_map.txt",
}

# Overrides set from config [prompts.files]
_PROMPT_FILE_OVERRIDES: dict[str, str] = {}


def _warn(msg: str) -> None:
    print(f"⚠️ {msg}", file=sys.stderr)


def set_prompt_file_overrides(mapping: dict[str, str] | None) -> None:
    """
    Public entry from main.py to inject config-specified files.

    RULES:
    - Only file-based prompts are supported.
    - If an override path is missing → warn and fall back to built-in.
    """
    global _PROMPT_FILE_OVERRIDES
    _PROMPT_FILE_OVERRIDES = dict(mapping or {})


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_prompt(key: str) -> str:
    """
    Loads prompt text with this priority:
    1) [prompts.files] override path (if exists)
    2) built-in file path (must exist)

    Errors are clear & user-facing.
    """
    # 1) override
    ov_path = _PROMPT_FILE_OVERRIDES.get(key)
    if ov_path:
        p = Path(ov_path)
        if p.exists():
            return _read_file(p)
        _warn(f"[prompts.files] path for key '{key}' not found: {ov_path} → falling back to built-in.")

    # 2) built-in
    builtin = BUILTIN_PROMPTS.get(key)
    if not builtin:
        raise ValueError(f"No built-in prompt for key: '{key}'. "
                         "Valid keys include: " + ", ".join(sorted(BUILTIN_PROMPTS.keys())))
    p = Path(builtin)
    if not p.exists():
        raise FileNotFoundError(
            f"Built-in prompt missing on disk for key '{key}' at {p!s}.\n"
            "Please ensure the repository includes default prompt files."
        )
    return _read_file(p)
