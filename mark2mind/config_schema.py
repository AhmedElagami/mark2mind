from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from pathlib import Path
import json, os

# Try TOML/YAML if present, but they’re optional
try:
    import tomllib as _toml  # Python 3.11+
except Exception:  # pragma: no cover
    _toml = None
try:
    import toml as _toml_backport  # fallback
except Exception:  # pragma: no cover
    _toml_backport = None
try:
    import yaml as _yaml
except Exception:  # pragma: no cover
    _yaml = None


class PathsConfig(BaseModel):
    input_file: Optional[str] = None
    output_dir: str = "output"
    debug_dir: str = "debug"
    file_id: Optional[str] = None


class ChunkConfig(BaseModel):
    tokenizer_name: str = "gpt2"
    max_tokens: int = 2000
    overlap_tokens: int = 0


class LLMConfig(BaseModel):
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    api_key_env: str = "DEEPSEEK_API_KEY"  # which env var to read
    api_key: Optional[str] = None          # optionally set in config, else env
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
    steps: List[str] = Field(default_factory=lambda: ["chunk","tree","cluster","merge","refine","map"])
    preset: Optional[str] = None

class SubtitlesConfig(BaseModel):
    # Step 1 (list)
    list_dir: Optional[str] = None              # root folder to scan
    file_list: str = "file_list.txt"            # where to write the list

    # Step 2 (merge)
    output_md: str = "merged_subtitles.md"      # merged markdown path

    # Shared
    enable_html: bool = False                   # include .html files

class PresetsConfig(BaseModel):
    named: Dict[str, List[str]] = {
        "reformat": ["chunk","reformat"],
        "clean_for_map": ["chunk","clean_for_map"],
        "qa": ["chunk","qa"],
        "full": ["chunk","tree","cluster","merge","refine","map"],
        # NEW:
        "subs_list": ["subs_list"],
        "subs_merge": ["subs_merge"],
    }

class AppConfig(BaseModel):
    paths: PathsConfig = PathsConfig()
    chunk: ChunkConfig = ChunkConfig()
    llm: LLMConfig = LLMConfig()
    tracing: TracingConfig = TracingConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    pipeline: PipelineConfig = PipelineConfig()
    presets: PresetsConfig = PresetsConfig()
    # NEW:
    subtitles: SubtitlesConfig = SubtitlesConfig()


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_config(path_like: Optional[str]) -> AppConfig:
    if not path_like:
        return AppConfig()
    p = Path(path_like)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path_like}")

    text = _load_text(p)
    suffix = p.suffix.lower()
    data = None

    if suffix in (".json",):
        data = json.loads(text)
    elif suffix in (".toml",):
        if _toml:
            data = _toml.loads(text)
        elif _toml_backport:
            data = _toml_backport.loads(text)
        else:
            raise RuntimeError("TOML requested but no tomllib/toml available. Install 'toml'.")
    elif suffix in (".yaml", ".yml"):
        if not _yaml:
            raise RuntimeError("YAML requested but PyYAML not installed. Install 'pyyaml'.")
        data = _yaml.safe_load(text)
    else:
        # default: try JSON
        data = json.loads(text)

    return AppConfig(**(data or {}))
