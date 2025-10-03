from __future__ import annotations
from typing import Dict
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from mark2mind.utils.chunker import chunk_markdown

class ChunkStage:
    ARTIFACT = "chunks.json"
    requires = ["input"]

    def run(
        self,
        ctx: RunContext,
        max_tokens: int,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        debug: bool,
        use_debug_io: bool,
    ) -> RunContext:
        if use_debug_io:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                ctx.chunks = loaded
                return ctx

        task = progress.start("Chunking markdown", total=1)
        ctx.chunks = chunk_markdown(ctx.text, max_tokens=max_tokens, debug=debug, debug_dir=store.debug_dir)
        if debug:
            store.save_debug(self.ARTIFACT, ctx.chunks)
        progress.advance(task); progress.finish(task)
        return ctx
