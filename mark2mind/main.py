from __future__ import annotations
from langchain import globals
globals.set_verbose(True)

import argparse
import os
import uuid
from datetime import datetime
from pathlib import Path

# Prevent transformer backend noise (same as before)
os.environ["TRANSFORMERS_NO_AVAILABLE_BACKENDS"] = "1"

from mark2mind.config_schema import load_config, AppConfig

from langchain_deepseek import ChatDeepSeek

# NEW imports: pipeline runner + config
from mark2mind.pipeline.core.config import RunConfig
from mark2mind.pipeline.runner import StepRunner

# keep your local tracer
from mark2mind.utils.tracing import LocalTracingHandler


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run semantic mindmap generation with Q&A from Markdown"
    )
    p.add_argument("input_file", nargs="?", type=str, help="Path to raw Markdown file")
    p.add_argument("file_id", nargs="?", type=str, help="Unique debug/output identifier")
    p.add_argument(
        "--steps",
        type=str,
        required=False,
        help="Comma-separated steps to run (e.g. chunk,bullets,qa,tree,cluster,merge,refine,map)",
     )
    p.add_argument("--preset", type=str, help="Named preset, e.g. reformat | clean_for_map | qa | full")
    p.add_argument("--config", type=str, help="Path to config file (.json/.toml/.yaml)")
    p.add_argument("--debug", action="store_true", help="Enable debug output and tracing")
    p.add_argument(
        "--force", action="store_true", help="Force re-run of steps (ignore cached artifacts)"
    )
    p.add_argument(
        "--enable-tracing",
        action="store_true",
        help="Enable local tracing to debug/traces",
    )
    p.add_argument(
        "--max-workers",
        type=int,
        default=20,
        help="Optional: ThreadPool max workers (default: library default)",
    )
    p.add_argument("--output-dir", type=str, help="Override output directory")
    p.add_argument("--debug-dir", type=str, help="Override debug directory")
    p.add_argument("--input", dest="input_override", type=str, help="Override input file (alternative to positional)")
    p.add_argument("--file-id", dest="file_id_override", type=str, help="Override file id (alternative to positional)")
    return p


def load_llm_from_config(app: AppConfig) -> ChatDeepSeek:
    # NOTE: current implementation uses DeepSeek. You can branch on app.llm.provider if needed.
    if app.llm.api_key:
        os.environ.setdefault(app.llm.api_key_env, app.llm.api_key)
    api_key = os.getenv(app.llm.api_key_env, "")
    if not api_key:
        raise RuntimeError(f"Missing API key: set {app.llm.api_key_env} or provide in config.llm.api_key")
    os.environ[app.llm.api_key_env] = api_key
    return ChatDeepSeek(
        model=app.llm.model,
        temperature=app.llm.temperature,
        max_tokens=app.llm.max_tokens,
        timeout=app.llm.timeout,
        max_retries=app.llm.max_retries,
    )


def main():
    args = build_parser().parse_args()

    app = load_config(args.config)

    # Merge CLI overrides into app config (CLI wins)
    if args.steps:
        app.pipeline.steps = [s.strip() for s in args.steps.split(",") if s.strip()]
        app.pipeline.preset = None
    elif args.preset:
        app.pipeline.preset = args.preset.strip()

    if args.output_dir:
        app.paths.output_dir = args.output_dir
    if args.debug_dir:
        app.paths.debug_dir = args.debug_dir
    if args.input_override or args.input_file:
        app.paths.input_file = args.input_override or args.input_file
    if args.file_id_override or args.file_id:
        app.paths.file_id = args.file_id_override or args.file_id

    steps = (app.presets.named.get(app.pipeline.preset, app.pipeline.steps)
             if app.pipeline.preset else app.pipeline.steps)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]

    tracer = (
        LocalTracingHandler(base_dir=app.paths.debug_dir, file_id=(app.paths.file_id or "run"), run_id=run_id)
        if (args.enable_tracing or app.tracing.enabled)
        else None
    )
    callbacks = [tracer] if tracer else None

    cfg = RunConfig.from_app(app)
    # final CLI overrides that aren’t in the config object
    if args.force:
        cfg.force = True
    if args.max_workers is not None:
        cfg.executor_max_workers = args.max_workers
    # ensure steps resolved above are pushed into cfg
    cfg.steps = steps
    # ensure run-time id and dirs
    cfg.run_id = run_id
    cfg.debug_dir = Path(app.paths.debug_dir)
    cfg.output_dir = Path(app.paths.output_dir)

    # Create & run the new StepRunner
    runner = StepRunner(
        config=cfg,
        debug=(args.debug or app.runtime.debug),
        callbacks=callbacks,
        llm_factory=lambda: load_llm_from_config(app),
    )

    runner.run()


if __name__ == "__main__":
    main()
