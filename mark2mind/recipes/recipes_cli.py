from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

from mark2mind.recipes import get_recipe_names, get_recipe_path

def run_mark2mind_with_config(cfg_path: Path, extra: list[str]) -> int:
    cmd = [sys.executable, "-m", "mark2mind", "--config", str(cfg_path)] + extra
    return subprocess.call(cmd)

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="m2m",
        description="mark2mind recipes runner (v2-min)"
    )
    p.add_argument("--recipe", required=True, choices=get_recipe_names(), help="Which recipe to run")
    p.add_argument("--input", dest="input_override", help="Override [io].input")
    p.add_argument("--run-name", dest="run_name_override", help="Override [io].run_name")
    p.add_argument("--preset", help="Override [pipeline].preset")
    p.add_argument("--steps", help="Override [pipeline].steps (comma-separated; wins over preset)")
    p.add_argument("--force", action="store_true", help="Force re-run")
    p.add_argument("--enable-tracing", action="store_true", help="Enable tracing")
    p.add_argument("--max-workers", type=int, help="Thread pool size")
    p.add_argument("--output-dir", help="Override [io].output_dir")
    p.add_argument("--debug-dir", help="Override [io].debug_dir")
    return p

def main():
    args = build_parser().parse_args()
    cfg = get_recipe_path(args.recipe)

    extra: list[str] = []
    if args.input_override:
        extra += ["--input", args.input_override]
    if args.run_name_override:
        extra += ["--run-name", args.run_name_override]
    if args.preset:
        extra += ["--preset", args.preset]
    if args.steps:
        extra += ["--steps", args.steps]
    if args.force:
        extra += ["--force"]
    if args.enable_tracing:
        extra += ["--enable-tracing"]
    if args.max_workers is not None:
        extra += ["--max-workers", str(args.max_workers)]
    if args.output_dir:
        extra += ["--output-dir", args.output_dir]
    if args.debug_dir:
        extra += ["--debug-dir", args.debug_dir]

    raise SystemExit(run_mark2mind_with_config(cfg, extra))

# --- Small wrapper entrypoints (map to fixed recipes) ------------------------

def _wrap(recipe: str):
    def _runner():
        # pass through all args after the command (e.g. --input ...)
        # we allow users to override input/run-name/etc even for wrappers
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--input")
        parser.add_argument("--run-name")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--enable-tracing", action="store_true")
        parser.add_argument("--max-workers", type=int)
        parser.add_argument("--output-dir")
        parser.add_argument("--debug-dir")
        known, unknown = parser.parse_known_args()

        cfg = get_recipe_path(recipe)
        extra: list[str] = []
        if known.input:
            extra += ["--input", known.input]
        if known.run_name:
            extra += ["--run-name", known.run_name]
        if known.force:
            extra += ["--force"]
        if known.enable_tracing:
            extra += ["--enable-tracing"]
        if known.max_workers is not None:
            extra += ["--max-workers", str(known.max_workers)]
        if known.output_dir:
            extra += ["--output-dir", known.output_dir]
        if known.debug_dir:
            extra += ["--debug-dir", known.debug_dir]
        # append unknown to keep compatibility with new flags later
        extra += unknown
        raise SystemExit(run_mark2mind_with_config(cfg, extra))
    return _runner

# Individual wrappers:
list_subs_main = _wrap("list_subtitles_in_dir")
merge_subs_main = _wrap("merge_subtitles_from_manifest")
reformat_main   = _wrap("reformat_markdown")
clarify_main    = _wrap("clarify_markdown")
mindmap_main    = _wrap("mindmap_from_markdown")
mindmapd_main   = _wrap("detailed_mindmap_from_markdown")
qa_main         = _wrap("qa_from_markdown")
