from __future__ import annotations
from concurrent.futures import as_completed
from typing import List, Tuple, Dict
from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider
from mark2mind.chains.format_bullets_chain import FormatBulletsChain

class BulletsStage:
    ARTIFACT = "bullets.json"
    requires: list[str] = []

    def __init__(self,
                 llm_pool: LLMFactoryPool,
                 retryer: Retryer,
                 callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks

    def _make_chain(self):
        llm = self.llm_pool.get()
        return FormatBulletsChain(llm, callbacks=self.callbacks)

    def run(self,
            ctx: RunContext,
            store: ArtifactStore,
            progress: ProgressReporter,
            *,
            executor: ExecutorProvider,   # ← accept executor like other stages
            use_debug_io: bool,
        ) -> RunContext:

        if use_debug_io:
            loaded = store.load_debug(self.ARTIFACT)
            if loaded is not None:
                setattr(ctx, "bullets_outputs", loaded)
                return ctx

        # Prepare work: (chunk_index, md_text)
        items: List[Tuple[int, str]] = [
            (i, (c.get("md_text") or "").strip())
            for i, c in enumerate(ctx.chunks)
            if (c.get("md_text") or "").strip()
        ]

        if not items:
            store.save_debug(self.ARTIFACT, [])
            setattr(ctx, "bullets_outputs", [])
            return ctx

        task = progress.start("Formatting bullets per chunk", total=len(items))

        # Per-task function: each worker grabs its own chain (thread-local LLM)
        def process(item: Tuple[int, str]) -> Dict:
            idx, text = item
            local_chain = self._make_chain()
            formatted = self.retryer.call(local_chain.invoke, text, config={"meta": f"bullets:{idx}"})
            return {"chunk_index": idx, "input_len": len(text), "markdown": formatted}

        outputs: List[Dict] = []
        with executor.get() as pool:
            futs = {pool.submit(process, it): it[0] for it in items}
            for fut in as_completed(futs):
                outputs.append(fut.result())
                progress.advance(task)

        progress.finish(task)

        outputs_sorted = sorted(outputs, key=lambda x: x["chunk_index"])
        store.save_debug(self.ARTIFACT, outputs_sorted)
        setattr(ctx, "bullets_outputs", outputs_sorted)
        return ctx
