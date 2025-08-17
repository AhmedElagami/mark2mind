from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from pathlib import Path
import json
import os
import sys

# --- TOML/YAML loaders (kept simple + deterministic) -------------------------
try:
    import tomllib as _toml  # Python 3.11+
except Exception:
    _toml = None
try:
    import toml as _toml_backport  # Python <=3.10
except Exception:
    _toml_backport = None
try:
    import yaml as _yaml
except Exception:
    _yaml = None


# =============================================================================
# v2-min CONFIG MODELS
# =============================================================================

class IOConfig(BaseModel):
    """
    v2-min single I/O section.

    WHY: Unified source of truth for input/output & subtitles options.
    """
    # Main entry: file or directory (mode is inferred)
    input: Optional[str] = None

    # Workspace roots; all artifacts write under <output_dir>/<run_name>/
    output_dir: str = "output"
    debug_dir: str = "debug"

    # Optional; auto-derived from input if omitted
    run_name: Optional[str] = None

    # Subtitles-only options (effective when input is a directory)
    manifest: str = "file_list.txt"   # subs_list writes; subs_merge reads
    include_html: bool = False


class ChunkConfig(BaseModel):
    tokenizer_name: str = "gpt2"
    max_tokens: int = 2000
    overlap_tokens: int = 0


class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key_env: str = "DEEPSEEK_API_KEY"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 8000
    timeout: Optional[float] = None
    max_retries: int = 2


class TracingConfig(BaseModel):
    enabled: bool = False
    traces_dir: str = "debug/traces"


class RuntimeConfig(BaseModel):
    force: bool = False
    debug: bool = False
    executor_max_workers: Optional[int] = 20
    min_delay_sec: float = 0.15
    max_retries: int = 4
    map_batch_override: Optional[int] = None


class PipelineConfig(BaseModel):
    steps: List[str] = Field(default_factory=lambda: ["chunk", "tree", "cluster", "merge", "refine", "map"])
    preset: Optional[str] = None


class PresetsConfig(BaseModel):
    named: Dict[str, List[str]] = {
        "reformat": ["chunk", "reformat"],
        "bullets": ["chunk", "bullets"],
        "clean_for_map": ["chunk", "clean_for_map"],
        "qa": ["chunk", "qa"],
        "mindmap": ["chunk", "tree", "cluster", "merge", "refine"],
        "detailed_mindmap": ["chunk", "tree", "cluster", "merge", "refine", "map"],
        "subs_list": ["subs_list"],
        "subs_merge": ["subs_merge"],
    }


class PromptsFilesConfig(BaseModel):
    """
    Only file-based prompts; keys -> file paths.
    If missing or file not found, we fall back to built-ins.
    """
    __root__: Dict[str, str] = Field(default_factory=dict)

    def get_map(self) -> Dict[str, str]:
        return dict(self.__root__)


class PromptsConfig(BaseModel):
    files: PromptsFilesConfig = PromptsFilesConfig()


class AppConfig(BaseModel):
    """
    v2-min top-level app config.
    """
    io: IOConfig = IOConfig()
    chunk: ChunkConfig = ChunkConfig()
    llm: LLMConfig = LLMConfig()
    tracing: TracingConfig = TracingConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    pipeline: PipelineConfig = PipelineConfig()
    presets: PresetsConfig = PresetsConfig()
    prompts: PromptsConfig = PromptsConfig()


# =============================================================================
# LOAD & NORMALIZE
# =============================================================================

def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _warn(msg: str) -> None:
    print(f"⚠️ {msg}", file=sys.stderr)


def _info(msg: str) -> None:
    print(f"ℹ️ {msg}", file=sys.stderr)


def _derive_run_name(input_path: Path) -> str:
    """
    WHY: mode is inferred; run_name is optional.
    """
    if input_path.is_dir():
        return input_path.name or "run"
    # file
    return input_path.stem or "run"


def _apply_legacy_mappings(raw: dict) -> dict:
    """
    Backwards compatibility layer:
    - Map [paths] and [subtitles] to v2-min [io].
    - Map legacy prompt loader (none in config) is fine (we have built-ins).
    """
    if not isinstance(raw, dict):
        return {}

    io = raw.get("io", {}) or {}

    # Map [paths] -> [io]
    if "paths" in raw:
        _warn("Legacy section [paths] detected; mapping to [io]. Please upgrade to v2-min.")
        legacy = raw.get("paths") or {}
        # input_file -> io.input
        if "input_file" in legacy and "input" not in io:
            io["input"] = legacy.get("input_file")
        # output_dir/debug_dir
        io.setdefault("output_dir", legacy.get("output_dir", "output"))
        io.setdefault("debug_dir", legacy.get("debug_dir", "debug"))
        # file_id -> io.run_name
        if "file_id" in legacy and "run_name" not in io:
            io["run_name"] = legacy.get("file_id")

    # Map [subtitles] -> [io] (subtitles-only options)
    if "subtitles" in raw:
        _warn("Legacy section [subtitles] detected; mapping to [io]. Please upgrade to v2-min.")
        subs = raw.get("subtitles") or {}
        # file_list -> manifest
        if "file_list" in subs and "manifest" not in io:
            io["manifest"] = subs.get("file_list")
        # enable_html -> include_html
        if "enable_html" in subs and "include_html" not in io:
            io["include_html"] = bool(subs.get("enable_html", False))

    # Attach back
    if io:
        raw["io"] = io

    return raw


def _parse_config_text(text: str, suffix: str) -> dict:
    if suffix == ".json":
        return json.loads(text)
    if suffix == ".toml":
        if _toml:
            return _toml.loads(text)
        if _toml_backport:
            return _toml_backport.loads(text)
        raise RuntimeError("TOML requested but no tomllib/toml available. Install 'toml'.")
    if suffix in (".yaml", ".yml"):
        if not _yaml:
            raise RuntimeError("YAML requested but PyYAML not installed. Install 'pyyaml'.")
        return _yaml.safe_load(text)
    # Default to JSON if unknown
    return json.loads(text)


def load_config(path_like: Optional[str]) -> AppConfig:
    """
    Loads, applies legacy mappings, and normalizes v2-min config.
    """
    raw: dict = {}
    if path_like:
        p = Path(path_like)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {path_like}")
        text = _load_text(p)
        raw = _parse_config_text(text, p.suffix.lower())
    else:
        # empty == defaults
        raw = {}

    # Legacy -> v2-min
    raw = _apply_legacy_mappings(raw)

    # Materialize into AppConfig (so we have defaults)
    app = AppConfig(**(raw or {}))

    # Validate/normalize I/O
    if not app.io.input:
        raise ValueError(
            "Config error: [io].input is required.\n"
            "Hint: set it to a Markdown file for mindmap/qa, or a directory for subtitles."
        )

    input_path = Path(app.io.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {app.io.input}")

    # Auto-derive run_name if omitted
    if not app.io.run_name:
        app.io.run_name = _derive_run_name(input_path)
        _info(f"[io].run_name not set → using '{app.io.run_name}'.")

    # Ensure basic strings (just in case)
    app.io.output_dir = app.io.output_dir or "output"
    app.io.debug_dir = app.io.debug_dir or "debug"
    app.io.manifest = app.io.manifest or "file_list.txt"

    return app
