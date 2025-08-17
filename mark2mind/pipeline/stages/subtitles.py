from __future__ import annotations

from pathlib import Path

from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from mark2mind.utils.subtitles import list_subtitle_files, merge_from_list


class SubtitlesListStage:
    """
    Writes the manifest to the exact path provided by the runner.
    """
    def run(
        self,
        ctx: RunContext,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        list_dir: str,
        manifest_path: str,
        enable_html: bool
    ) -> RunContext:
        task = progress.start(f"Listing subtitles in: {list_dir}", total=1)
        out = list_subtitle_files(list_dir, manifest_path, enable_html=enable_html)
        # Also mirror into workspace relative (if possible)
        p = Path(out)
        if p.exists():
            rel = p.name if p.parent == store.workspace_dir else f"subs/{p.name}"
            store.write_text(rel, p.read_text(encoding="utf-8"))
        progress.advance(task); progress.finish(task)
        return ctx


class SubtitlesMergeStage:
    """
    Consumes manifest and writes a single merged Markdown output.
    """
    def run(
        self,
        ctx: RunContext,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        manifest_path: str,
        output_md: str,
        enable_html: bool
    ) -> RunContext:
        task = progress.start(f"Merging from manifest: {manifest_path}", total=1)
        if not Path(manifest_path).exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}\n"
                                    "Hint: run subs_list first to generate it.")
        out = merge_from_list(manifest_path, output_md, enable_html=enable_html)
        p = Path(out)
        store.write_text(p.name, p.read_text(encoding="utf-8"))
        progress.advance(task); progress.finish(task)
        return ctx
