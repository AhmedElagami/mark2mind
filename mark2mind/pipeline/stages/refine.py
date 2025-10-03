from __future__ import annotations
from concurrent.futures import as_completed
from typing import Dict, List
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider
from mark2mind.chains.merge_tree_chain import TreeMergeChain
from mark2mind.chains.refine_tree_chain import TreeRefineChain
from mark2mind.utils.tree_helper import assign_node_ids

class RefineStage:
    ARTIFACT = "refined_tree.json"
    requires: list[str] = []

    def __init__(self, llm_pool: LLMFactoryPool, retryer: Retryer, callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks
    def _make_chains(self):
        llm = self.llm_pool.get()
        return TreeMergeChain(llm, callbacks=self.callbacks), TreeRefineChain(llm, callbacks=self.callbacks)

    def _merge_all_parallel(self, trees: List[Dict], merge_chain: TreeMergeChain, executor: ExecutorProvider):
        cur = [t for t in trees if t]
        round_idx = 0
        while len(cur) > 1:
            pairs = [(cur[i], cur[i + 1]) for i in range(0, len(cur) - 1, 2)]
            leftovers = [cur[-1]] if len(cur) % 2 == 1 else []

            def merge_pair(j_ab):
                j, (a, b) = j_ab
                local_merge_chain, _ = self._make_chains()
                return self.retryer.call(local_merge_chain.invoke, a, b, config={"meta": f"merge:refine:{round_idx}:{j}"})

            if pairs:
                merged_by_idx = {}
                with executor.get() as pool:
                    fut_map = {pool.submit(merge_pair, (j, ab)): j for j, ab in enumerate(pairs)}
                    for f in as_completed(fut_map):
                        j = fut_map[f]; merged_by_idx[j] = f.result()
                merged = [merged_by_idx[j] for j in range(len(pairs))]
            else:
                merged = []

            cur = merged + leftovers
            round_idx += 1

        return cur[0]

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
                ctx.final_tree = loaded
                return ctx

        merge_chain, refine_chain = self._make_chains()

        task = progress.start("Refining", total=2)
        merged = self._merge_all_parallel(ctx.cluster_trees, merge_chain, executor)
        progress.advance(task)
        if not merged:
            progress.finish(task)
            return ctx

        refined = self.retryer.call(refine_chain.invoke, merged)
        progress.advance(task); progress.finish(task)
        assign_node_ids(refined)
        ctx.final_tree = refined
        store.save_debug(self.ARTIFACT, refined)
        return ctx
