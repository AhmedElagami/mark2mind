from __future__ import annotations
from pathlib import Path
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from mark2mind.utils.subtitles import list_subtitle_files, merge_from_list

class SubtitlesListStage:
    def run(self, ctx: RunContext, store: ArtifactStore, progress: ProgressReporter, *, list_dir: str, file_list: str, enable_html: bool) -> RunContext:
        task = progress.start(f"Listing subtitles in: {list_dir}", total=1)
        out = list_subtitle_files(list_dir, file_list, enable_html=enable_html)
        store.write_text(Path(out).name, Path(out).read_text(encoding="utf-8"))
        progress.advance(task); progress.finish(task)
        return ctx

class SubtitlesMergeStage:
    def run(self, ctx: RunContext, store: ArtifactStore, progress: ProgressReporter, *, file_list: str, output_md: str, enable_html: bool) -> RunContext:
        task = progress.start(f"Merging from list: {file_list}", total=1)
        out = merge_from_list(file_list, output_md, enable_html=enable_html)
        # copy merged file into output dir for convenience
        p = Path(out)
        store.write_text(p.name, p.read_text(encoding="utf-8"))
        progress.advance(task); progress.finish(task)
        return ctx
