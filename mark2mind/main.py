from __future__ import annotations

import argparse
import os
import uuid
from datetime import datetime
from pathlib import Path

# Prevent transformer backend noise (same as before)
os.environ["TRANSFORMERS_NO_AVAILABLE_BACKENDS"] = "1"

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
    p.add_argument("input_file", type=str, help="Path to raw Markdown file")
    p.add_argument("file_id", type=str, help="Unique debug/output identifier")
    p.add_argument(
        "--steps",
        type=str,
        required=True,
        help="Comma-separated steps to run (e.g. chunk,bullets,qa,tree,cluster,merge,refine,map)",
    )
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
    return p


def load_llm() -> ChatDeepSeek:
    """
    Factory that returns a fresh LLM client.
    The pipeline will call this per worker thread to avoid sharing clients across threads.
    """
    # Prefer env var; falls back to existing env if set elsewhere
    # e.g., export DEEPSEEK_API_KEY=sk-...
    api_key = "sk-06a8bbe5dd014a6aac5b4c182c06640e"

    # langchain_deepseek reads key from env, but we set again for clarity
    os.environ["DEEPSEEK_API_KEY"] = api_key

    return ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.3,
        max_tokens=8000,
        timeout=None,
        max_retries=2,
    )


def main():
    args = build_parser().parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]

    tracer = (
        LocalTracingHandler(base_dir="debug", file_id=args.file_id, run_id=run_id)
        if args.enable_tracing
        else None
    )
    callbacks = [tracer] if tracer else None

    # Build pipeline config
    cfg = RunConfig(
        file_id=args.file_id,
        input_file=Path(args.input_file),
        steps=steps,
        force=args.force,
    )
    # allow tuning worker count from CLI
    cfg.executor_max_workers = args.max_workers

    # Create & run the new StepRunner
    runner = StepRunner(
        config=cfg,
        debug=args.debug,
        callbacks=callbacks,
        # give the pipeline a factory so each worker gets its own LLM client
        llm_factory=load_llm,
        # we *could* also pass prebuilt chain instances, but with llm_factory that’s unnecessary
    )

    runner.run()


if __name__ == "__main__":
    main()
