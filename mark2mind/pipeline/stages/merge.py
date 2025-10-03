from __future__ import annotations
from concurrent.futures import as_completed
from typing import Dict, List, Tuple
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider
from mark2mind.chains.merge_tree_chain import TreeMergeChain

class MergeStage:
    ARTIFACT = "merged_clusters.json"
    requires: list[str] = []

    def __init__(self, llm_pool: LLMFactoryPool, retryer: Retryer, callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks

    def _make_chain(self):
        llm = self.llm_pool.get()
        return TreeMergeChain(llm, callbacks=self.callbacks)

    def _merge_round(self, trees: List[Dict], chain: TreeMergeChain, tag_prefix: str) -> List[Dict]:
        pairs = [(trees[i], trees[i + 1]) for i in range(0, len(trees) - 1, 2)]
        leftovers = [trees[-1]] if len(trees) % 2 == 1 else []
        merged_by_idx = []
        for j, (a, b) in enumerate(pairs):
            merged = self.retryer.call(chain.invoke, a, b, config={"meta": f"{tag_prefix}:{j}"})
            merged_by_idx.append(merged)
        return merged_by_idx + leftovers

    def _merge_group_parallel(self, cid_group: Tuple[int, List[Dict]], chain: TreeMergeChain, executor: ExecutorProvider):
        cid, group = cid_group
        trees = [i["tree"] for i in group if i.get("tree")]
        round_idx = 0
        while len(trees) > 1:
            pairs = [(trees[i], trees[i + 1]) for i in range(0, len(trees) - 1, 2)]
            leftovers = [trees[-1]] if len(trees) % 2 == 1 else []

            def merge_pair(j_ab):
                j, (a, b) = j_ab
                local_chain = self._make_chain()
                return self.retryer.call(local_chain.invoke, a, b, config={"meta": f"merge:{cid}:{round_idx}:{j}"})

            if pairs:
                merged_by_idx = {}
                with executor.get() as pool:
                    fut_map = {pool.submit(merge_pair, (j, ab)): j for j, ab in enumerate(pairs)}
                    for f in as_completed(fut_map):
                        j = fut_map[f]
                        merged_by_idx[j] = f.result()
                merged = [merged_by_idx[j] for j in range(len(pairs))]
            else:
                merged = []

            trees = merged + leftovers
            round_idx += 1

        return trees[0] if trees else None

    def run(
        self,
        ctx: RunContext,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        executor: ExecutorProvider,
        use_debug_io: bool,
    ) -> RunContext:
        if use_debug_io:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                ctx.cluster_trees = loaded
                return ctx

        chain = self._make_chain()
        items = list(enumerate(ctx.clustered))
        task = progress.start("Merging clusters", total=len(items))

        trees: List[Dict] = []
        with executor.get() as pool:
            futs = {pool.submit(self._merge_group_parallel, item, chain, executor): item for item in items}
            for fut in as_completed(futs):
                trees.append(fut.result()); progress.advance(task)

        ctx.cluster_trees = [t for t in trees if t]
        store.save_debug(self.ARTIFACT, ctx.cluster_trees)
        progress.finish(task)
        return ctx
