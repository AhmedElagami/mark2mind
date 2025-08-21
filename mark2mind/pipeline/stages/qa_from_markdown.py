from __future__ import annotations
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from mark2mind.utils.qa_parser import parse_qa_markdown

class QAFromMarkdownStage:
    ARTIFACT = "qa_blocks.json"

    def run(self, ctx: RunContext, store: ArtifactStore, progress: ProgressReporter, *, force: bool) -> RunContext:
        if not force:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                setattr(ctx, "qa_blocks", loaded)
                setattr(ctx, "qa_only_map", True)
                return ctx

        task = progress.start("Parsing QA markdown", total=1)
        qa_blocks = parse_qa_markdown(ctx.text)
        setattr(ctx, "qa_blocks", qa_blocks)
        setattr(ctx, "qa_only_map", True)   # tell MapContentStage to skip normal blocks
        store.save_debug(self.ARTIFACT, qa_blocks)
        progress.advance(task)
        progress.finish(task)
        return ctx
