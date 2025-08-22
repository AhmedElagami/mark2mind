from __future__ import annotations
from typing import List
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter

class ClusterStage:
    ARTIFACT = "clusters.json"

    def run(
        self,
        ctx: RunContext,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        use_debug_io: bool,
    ) -> RunContext:
        if use_debug_io:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                ctx.clustered = loaded
                return ctx

        progress_task = progress.start("Clustering chunks", total=1)
        n = len(ctx.chunk_results)
        if n <= 1:
            ctx.clustered = [ctx.chunk_results]
        else:
            from mark2mind.utils.clustering import cluster_chunk_trees
            ctx.clustered = cluster_chunk_trees(ctx.chunk_results, None)
        store.save_debug(self.ARTIFACT, ctx.clustered)
        progress.advance(progress_task); progress.finish(progress_task)
        return ctx
