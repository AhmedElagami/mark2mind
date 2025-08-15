from __future__ import annotations
from concurrent.futures import as_completed
from typing import Dict, List, Tuple
import math

from ..core.context import RunContext
from ..core.artifacts import ArtifactStore
from ..core.progress import ProgressReporter
from ..core.retry import Retryer
from ..core.llm_pool import LLMFactoryPool
from ..core.executor_provider import ExecutorProvider

from mark2mind.chains.map_content_mindmap_chain import ContentMappingChain
from mark2mind.utils.tree_helper import insert_content_refs_into_tree


class MapContentStage:
    FINAL_TREE_ARTIFACT = "final_tree.json"

    def __init__(
        self,
        llm_pool: LLMFactoryPool,
        retryer: Retryer,
        callbacks=None,
        chain_instance: ContentMappingChain | None = None,
    ):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks
        self.chain_instance = chain_instance

    def _make_chain(self):
        llm = self.llm_pool.get()
        if llm is None:
            return self.chain_instance
        return ContentMappingChain(llm, callbacks=self.callbacks)

    def _mk_caption(self, b: Dict) -> str:
        # Make captions more informative for images so the LLM can place them
        if b.get("type") == "image":
            alt = (b.get("alt") or "").strip() or "Image"
            hp = b.get("heading_path") or []
            trail = " / ".join(hp[-3:])
            caption = f"{alt} — {trail}" if trail else alt
            return caption # keep it generous for the model
        # Fallbacks for non-image content (original behavior with slight polish)
        txt = (b.get("text") or b.get("markdown") or "").strip()
        if txt:
            return txt.splitlines()[0][:160]
        hp = b.get("heading_path") or []
        return (" / ".join(hp[-2:]) if hp else "Content block")[:160]

    def _choose_batch_size(self, n: int, override: int | None) -> int:
        if override:
            return max(1, int(override))
        target_batches = min(max(6, round(n / 60)), 10)
        batch = max(1, math.ceil(n / max(1, target_batches)))
        return max(20, min(80, batch)) if n >= 20 else n

    def run(
        self,
        ctx: RunContext,
        store: ArtifactStore,
        progress: ProgressReporter,
        *,
        executor: ExecutorProvider,
        force: bool,
        map_batch_override: int | None,
    ) -> RunContext:
        if not ctx.final_tree:
            return ctx

        supported_types = {"paragraph", "code", "table", "image"}

        # ---------- Visibility / Telemetry ----------
        skip_log = {"no_id": [], "dup_id": [], "unsupported_type": []}
        queued_log: List[Dict] = []
        per_batch_log: Dict[int, List[str]] = {}
        mapped_log: List[Dict] = []
        # -------------------------------------------

        # Build unique list of blocks eligible for mapping
        seen, unique_blocks = set(), []
        for ch_i, ch in enumerate(ctx.chunks):
            for b in ch.get("blocks", []):
                eid = b.get("element_id")
                btype = b.get("type")

                if not eid:
                    sample = b.get("markdown") or b.get("src") or b.get("text") or ""
                    skip_log["no_id"].append(
                        {
                            "chunk_index": ch_i,
                            "type": btype,
                            "sample": sample[:200],
                        }
                    )
                    continue

                if btype not in supported_types:
                    skip_log["unsupported_type"].append(
                        {"chunk_index": ch_i, "id": eid, "type": btype}
                    )
                    continue

                if eid in seen:
                    skip_log["dup_id"].append(
                        {"chunk_index": ch_i, "id": eid, "type": btype}
                    )
                    continue

                seen.add(eid)

                payload = {
                    "element_id": eid,
                    "type": btype,
                    "element_caption": b.get("element_caption") or self._mk_caption(b),
                    "markdown": b.get("markdown") or b.get("text") or b.get("src") or "",
                    "is_atomic": b.get("is_atomic", False),
                    # Helpful context for mapping / debugging:
                    "heading_path": b.get("heading_path", []),
                    "source_chunk_index": ch_i,
                }

                # Keep mapping prompt small for images with huge src
                if btype == "image":
                    alt = (b.get("alt") or "").strip()
                    src = b.get("src") or ""
                    if src.startswith("data:"):
                        payload["markdown"] = f"![{alt}]([data-url])"
                    elif len(src) > 200:
                        payload["markdown"] = f"![{alt}]({src[:200]}…)"
                    # else keep as-is

                unique_blocks.append(payload)

        # Persist visibility artifacts: skips and queue
        store.save_debug("map_skips.json", skip_log)
        store.save_debug("map_queue.json", unique_blocks)
        queued_log = list(unique_blocks)  # (for symmetry; not strictly required)

        if not unique_blocks:
            store.save_debug(self.FINAL_TREE_ARTIFACT, ctx.final_tree)
            return ctx

        total = len(unique_blocks)
        batch_size = self._choose_batch_size(total, map_batch_override)
        num_batches = math.ceil(total / batch_size)
        batches = [
            (i // batch_size, unique_blocks[i : i + batch_size])
            for i in range(0, total, batch_size)
        ]

        task_batches = progress.start(
            f"Mapping content batches (≈{batch_size}, {num_batches} batches)",
            total=num_batches,
        )

        def run_batch(payload: Tuple[int, List[Dict]]):
            bidx, items = payload
            local_chain = self._make_chain()
            # Track which items are in this batch
            per_batch_log[bidx] = [it["element_id"] for it in items]
            mapped = self.retryer.call(
                local_chain.invoke,
                ctx.final_tree,
                items,
                config={"meta": f"map:{bidx+1}/{num_batches}"},
            )
            # Filter to complete rows only
            mapped = [
                m for m in mapped if m.get("element_id") and m.get("target_node_id")
            ]
            return (bidx, mapped)

        results_by_batch: Dict[int, List[Dict]] = {}
        with executor.get() as pool:
            futs = {pool.submit(run_batch, item): item[0] for item in batches}
            for fut in as_completed(futs):
                bidx, mapped = fut.result()
                results_by_batch[bidx] = mapped
                progress.advance(task_batches)

        # Combine mapped
        all_mapped: List[Dict] = []
        for i in range(num_batches):
            all_mapped.extend(results_by_batch.get(i, []))

        # Persist raw mapped rows
        for m in all_mapped:
            mapped_log.append(
                {
                    "element_id": m.get("element_id"),
                    "target_node_id": m.get("target_node_id"),
                }
            )
        store.save_debug("map_mapped_raw.json", mapped_log)
        store.save_debug("map_batches.json", per_batch_log)

        # Deduplicate mapped by element_id (first wins)
        deduped, seen_ids = [], set()
        for m in all_mapped:
            if m["element_id"] in seen_ids:
                continue
            seen_ids.add(m["element_id"])
            deduped.append(m)

        # Compute UNMAPPED: queued but not returned by LLM
        queued_ids = {u["element_id"] for u in unique_blocks}
        mapped_ids = {m["element_id"] for m in deduped}
        unmapped_ids = sorted(list(queued_ids - mapped_ids))
        unmapped_records = [u for u in unique_blocks if u["element_id"] in unmapped_ids]
        store.save_debug(
            "map_unmapped.json",
            {
                "count": len(unmapped_records),
                "items": unmapped_records,
            },
        )

        # Enrichment step
        id_to_block: Dict[str, Dict] = {}
        for ch in ctx.chunks:
            for b in ch.get("blocks", []):
                if eid := b.get("element_id"):
                    id_to_block[eid] = b

        task_enrich = progress.start("Enriching mapped refs", total=len(deduped))
        for m in deduped:
            b = id_to_block.get(m["element_id"])
            if b:
                btype = b.get("type")
                if btype == "code":
                    m["markdown"] = (
                        b.get("markdown")
                        or f"```{b.get('language','')}\n{b.get('text','')}\n```"
                    )
                elif btype == "table":
                    m["markdown"] = b.get("text", "") or ""
                elif btype == "image":
                    alt = (b.get("alt") or m.get("element_caption") or "image").strip()
                    src = b.get("src", "") or ""
                    m["markdown"] = f"![{alt}]({src})"
                else:
                    m["markdown"] = b.get("markdown") or b.get("text") or ""
            progress.advance(task_enrich)
        progress.finish(task_enrich)

        # Persist the final enriched mappings as well
        store.save_debug("map_mapped_final.json", deduped)

        # Insert into tree and persist final tree
        insert_content_refs_into_tree(ctx.final_tree, deduped)
        store.save_debug(self.FINAL_TREE_ARTIFACT, ctx.final_tree)
        return ctx
