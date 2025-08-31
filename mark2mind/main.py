from __future__ import annotations

from langchain import globals as lc_globals
lc_globals.set_verbose(True)

import argparse
import os
import uuid
from datetime import datetime
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

from mark2mind.config_schema import _derive_run_name, load_config, AppConfig
from langchain_deepseek import ChatDeepSeek

from mark2mind.pipeline.core.config import RunConfig
from mark2mind.pipeline.runner import StepRunner
from mark2mind.utils.tracing import LocalTracingHandler
from mark2mind.utils.prompt_loader import set_prompt_file_overrides

# NEW: allow single entry point to drive built-in recipes, too
from mark2mind.recipes import get_recipe_names, get_recipe_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="mark2mind: Mindmap/Q&A and subtitles pipelines (single CLI)."
    )

    # Choose ONE of: a config file OR a built-in recipe
    p.add_argument("--config", type=str, help="Path to config file (.toml/.json/.yaml)")
    p.add_argument(
        "--recipe",
        type=str,
        choices=get_recipe_names(),
        help="Built-in recipe name (use --list-recipes to see all)",
    )
    p.add_argument(
        "--list-recipes", action="store_true", help="List built-in recipes and exit"
    )

    # Common overrides
    p.add_argument("--input", dest="input_override", type=str, help="Override [io].input")
    p.add_argument("--input-qa", dest="input_qa", type=str, help="QA markdown input (for map_qa_onto_markmap)")
    p.add_argument("--input-markmap", dest="input_markmap", type=str, help="Existing Markmap markdown to import")
    p.add_argument("--run-name", dest="run_name_override", type=str, help="Override [io].run_name")
    p.add_argument("--output-dir", type=str, help="Override [io].output_dir")
    p.add_argument("--debug-dir", type=str, help="Override [io].debug_dir")

    # Pipeline selection
    p.add_argument("--steps", type=str, help="Comma-separated steps to run (steps wins over preset)")
    p.add_argument(
        "--preset",
        type=str,
        help="Preset name (qa|mindmap|detailed_mindmap|subs_list|subs_merge)"
    )

    # Runtime/debug
    p.add_argument("--debug", action="store_true", help="Enable verbose debug")
    p.add_argument(
        "--use-debug-io",
        action="store_true",
        help="Use cached artifacts from debug/<run_name> if present",
    )
    p.add_argument(
        "--enable-tracing",
        action="store_true",
        help="Enable local tracing in debug/<run_name>/traces",
    )
    p.add_argument("--max-workers", type=int, default=None, help="ThreadPool max workers")

    return p


def load_llm_from_config(app: AppConfig) -> ChatDeepSeek:
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
    parser = build_parser()
    import sys
    args = parser.parse_args()

    # List and exit
    if args.list_recipes:
        print("Available recipes:")
        for name in get_recipe_names():
            print(f"  - {name}")
        sys.exit(0)

    # Require one of --config or --recipe (but allow --input-only default if you want later)
    if not args.config and not args.recipe:
        parser.print_help()
        sys.exit(0)

    # Load config from built-in recipe OR from file
    if args.recipe:
        cfg_path = str(get_recipe_path(args.recipe))
        app = load_config(cfg_path)
    else:
        app = load_config(args.config)

    # Overrides
    if args.input_override:
        app.io.input = args.input_override
    if args.input_qa:
        app.io.input = args.input_qa
    if args.input_markmap:
        app.io.markmap_input = args.input_markmap
    # ✅ validate now, after overrides
    if not app.io.input:
        raise ValueError(
            "Missing input. Use [io].input in config or pass --input."
        )

    input_path = Path(app.io.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {app.io.input}")

    need_markmap = "import_markmap" in app.pipeline.steps
    if need_markmap and not app.io.markmap_input:
        raise ValueError("Missing Markmap input. Use --input-markmap")
    if app.io.markmap_input:
        markmap_path = Path(app.io.markmap_input)
        if not markmap_path.exists():
            raise FileNotFoundError(f"Markmap input not found: {app.io.markmap_input}")

    if not app.io.run_name:
        app.io.run_name = _derive_run_name(input_path)
    if args.run_name_override:
        app.io.run_name = args.run_name_override
    
    if args.output_dir:
        app.io.output_dir = args.output_dir
    if args.debug_dir:
        app.io.debug_dir = args.debug_dir

    if args.steps:
        app.pipeline.steps = [s.strip() for s in args.steps.split(",") if s.strip()]
        app.pipeline.preset = None
    elif args.preset:
        app.pipeline.preset = args.preset.strip()

    # Prompts: allow per-run file overrides while keeping built-ins bundled
    set_prompt_file_overrides(app.prompts.files.get_map())

    # Run id / tracing
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    tracer = None
    if args.enable_tracing or app.tracing.enabled:
        tracer = LocalTracingHandler(
            base_dir=app.io.debug_dir, file_id=(app.io.run_name or "run"), run_id=run_id
        )
    callbacks = [tracer] if tracer else None

    # Prepare RunConfig
    cfg = RunConfig.from_app(app)
    cfg.run_id = run_id
    if args.use_debug_io:
        cfg.use_debug_io = True
    if args.max_workers is not None:
        cfg.executor_max_workers = args.max_workers

    # Build runner
    runner = StepRunner(
        config=cfg,
        debug=(args.debug or app.runtime.debug),
        callbacks=callbacks,
        llm_factory=lambda: load_llm_from_config(app),
    )

    runner.run()


if __name__ == "__main__":
    main()
