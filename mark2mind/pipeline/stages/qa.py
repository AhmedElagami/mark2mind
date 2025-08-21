from __future__ import annotations
from concurrent.futures import as_completed
from typing import Dict, List, Tuple
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider

from mark2mind.chains.generate_questions_chain import GenerateQuestionsChain
from mark2mind.chains.answer_questions_chain import AnswerQuestionsChain

class QAStage:
    ARTIFACT = "chunks_with_qa.json"

    def __init__(self, llm_pool: LLMFactoryPool, retryer: Retryer, callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks

    def _make_chains(self):
        llm = self.llm_pool.get()
        return {
            "qa_q": GenerateQuestionsChain(llm, callbacks=self.callbacks),
            "qa_a": AnswerQuestionsChain(llm, callbacks=self.callbacks),
        }

    def run(self, ctx: RunContext, store: ArtifactStore, progress: ProgressReporter, *, executor: ExecutorProvider, force: bool) -> RunContext:
        if not force:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                ctx.chunks = loaded
                return ctx

        items = list(enumerate(ctx.chunks))
        task = progress.start("Q&A per chunk", total=len(items))

        def add_qa(idx_chunk):
            idx, chunk = idx_chunk
            chains = self._make_chains()
            questions = self.retryer.call(chains["qa_q"].invoke, chunk, config={"meta": f"qa-q:{idx}"})
            answers = self.retryer.call(chains["qa_a"].invoke, chunk, questions, config={"meta": f"qa-a:{idx}"})
            id_map = {b["element_id"]: b for b in chunk["blocks"]}
            for b in chunk["blocks"]:
                b.setdefault("qa_pairs", [])
            for qa in answers:
                eid = qa.get("element_id")
                if eid in id_map:
                    id_map[eid]["qa_pairs"].append(qa)
            return (idx, chunk)

        updated: List[Tuple[int, Dict]] = []
        with executor.get() as pool:
            futures = {pool.submit(add_qa, item): item for item in items}
            for fut in as_completed(futures):
                updated.append(fut.result())
                progress.advance(task)

        ctx.chunks = [chunk for _, chunk in sorted(updated, key=lambda x: x[0])]
        store.save_debug(self.ARTIFACT, ctx.chunks)
        progress.finish(task)
        return ctx
