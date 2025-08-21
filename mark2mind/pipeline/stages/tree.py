from __future__ import annotations
from concurrent.futures import as_completed
from collections import Counter
from typing import Dict, List, Tuple
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider
from mark2mind.chains.generate_tree_chain import ChunkTreeChain

class TreeStage:
    ARTIFACT = "chunk_trees.json"

    def __init__(self, llm_pool: LLMFactoryPool, retryer: Retryer, callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks

    def _make_chain(self):
        llm = self.llm_pool.get()
        return ChunkTreeChain(llm, callbacks=self.callbacks)

    def _chunk_heading_summary(self, chunk: Dict) -> List[str]:
        c = Counter()
        for b in chunk.get("blocks", []):
            path = " › ".join(b.get("heading_path") or [])
            c[path] += int(b.get("token_count", 0)) or 1
        return [p for p,_ in c.most_common(3)]

    def run(self, ctx: RunContext, store: ArtifactStore, progress: ProgressReporter, *, executor: ExecutorProvider, force: bool) -> RunContext:
        if not force:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                ctx.chunk_results = loaded
            return ctx

        items = list(enumerate(ctx.chunks))
        task = progress.start("Trees per chunk", total=len(items))

        def process(idx_chunk):
            idx, chunk = idx_chunk
            # Build a fresh chain in this worker/thread
            chain = self._make_chain()
            out = self.retryer.call(chain.invoke, chunk, config={"meta": f"tree:{idx}"})
            return {
                **out,
                "metadata": {
                    **chunk.get("metadata", {}),
                    "heading_paths_top": self._chunk_heading_summary(chunk),
                }
            }

        results: List[Dict] = []
        with executor.get() as pool:
            futures = {pool.submit(process, item): item for item in items}
            for fut in as_completed(futures):
                results.append(fut.result())
                progress.advance(task)

        ctx.chunk_results = results
        store.save_debug(self.ARTIFACT, ctx.chunk_results)
        progress.finish(task)
        return ctx