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
from mark2mind.chains.map_content_mindmap_qa_chain import QAContentMappingChain
from mark2mind.utils.tree_helper import insert_content_refs_into_tree

class MapContentStage:
    FINAL_TREE_ARTIFACT = "final_tree.json"

    def __init__(
        self,
        llm_pool: LLMFactoryPool,
        retryer: Retryer,
        callbacks=None):
        self.llm_pool = llm_pool
        self.retryer = retryer
        self.callbacks = callbacks

    def _make_chain_normal(self):
        llm = self.llm_pool.get()
        return ContentMappingChain(llm, callbacks=self.callbacks)

    def _make_chain_qa(self):
        llm = self.llm_pool.get()
        return QAContentMappingChain(llm, callbacks=self.callbacks)

    def _mk_caption(self, b: Dict) -> str:
        if b.get("type") == "image":
            alt = (b.get("alt") or "").strip() or "Image"
            hp = b.get("heading_path") or []
            trail = " / ".join(hp[-3:])
            caption = f"{alt} — {trail}" if trail else alt
            return caption
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

        qa_only = bool(getattr(ctx, "qa_only_map", False))

        supported_types_normal = {"paragraph", "code", "table", "image"}
        skip_log = {"no_id": [], "dup_id": [], "unsupported_type": []}
        seen = set()
        normal_blocks: List[Dict] = []
        qa_blocks: List[Dict] = []

        def enqueue_normal(b: Dict, ch_i: int | None):
            eid = b.get("element_id")
            btype = b.get("type")
            if not eid:
                sample = b.get("markdown") or b.get("src") or b.get("text") or ""
                skip_log["no_id"].append({"chunk_index": ch_i, "type": btype, "sample": sample[:200]})
                return
            if btype not in supported_types_normal:
                skip_log["unsupported_type"].append({"chunk_index": ch_i, "id": eid, "type": btype})
                return
            if eid in seen:
                skip_log["dup_id"].append({"chunk_index": ch_i, "id": eid, "type": btype})
                return
            seen.add(eid)
            payload = {
                "element_id": eid,
                "type": btype,
                "element_caption": b.get("element_caption") or self._mk_caption(b),
                "markdown": b.get("markdown") or b.get("text") or b.get("src") or "",
                "is_atomic": b.get("is_atomic", False),
                "heading_path": b.get("heading_path", []),
                "source_chunk_index": ch_i if ch_i is not None else -1,
            }
            if btype == "image":
                alt = (b.get("alt") or "").strip()
                src = b.get("src") or ""
                if src.startswith("data:"):
                    payload["markdown"] = f"![{alt}]([data-url])"
                elif len(src) > 200:
                    payload["markdown"] = f"![{alt}]({src[:200]}…)"
            normal_blocks.append(payload)

        def enqueue_qa(b: Dict):
            if (b.get("type") or "").lower() != "qa":
                return
            eid = b.get("element_id")
            if not eid or eid in seen:
                return
            seen.add(eid)
            qa_blocks.append({
                "element_id": eid,
                "type": "qa",
                "q": b.get("q") or "",
                "a": b.get("a") or "",
                "heading_path": b.get("heading_path", []),
            })

        if not qa_only:
            for ch_i, ch in enumerate(ctx.chunks):
                for b in ch.get("blocks", []):
                    enqueue_normal(b, ch_i)

        for b in getattr(ctx, "qa_blocks", []) or []:
            enqueue_qa(b)

        store.save_debug("map_skips.json", skip_log)
        store.save_debug("map_queue_normal.json", normal_blocks)
        store.save_debug("map_queue_qa.json", qa_blocks)

        mapped_all: List[Dict] = []

        # normal content mapping
        if normal_blocks and not qa_only:
            total = len(normal_blocks)
            batch_size = self._choose_batch_size(total, map_batch_override)
            num_batches = math.ceil(total / batch_size)
            batches = [(i // batch_size, normal_blocks[i:i+batch_size]) for i in range(0, total, batch_size)]
            task_n = progress.start(
                f"Mapping normal content (≈{batch_size}, {num_batches} batches)", total=num_batches
            )

            def run_batch_normal(payload: Tuple[int, List[Dict]]):
                bidx, items = payload
                chain = self._make_chain_normal()
                mapped = self.retryer.call(chain.invoke, ctx.final_tree, items, config={"meta": f"map:norm:{bidx+1}/{num_batches}"})
                mapped = [m for m in mapped if m.get("element_id") and m.get("target_node_id")]
                return (bidx, mapped)

            results_by_batch: Dict[int, List[Dict]] = {}
            with executor.get() as pool:
                futs = {pool.submit(run_batch_normal, item): item[0] for item in batches}
                for fut in as_completed(futs):
                    bidx, mapped = fut.result()
                    results_by_batch[bidx] = mapped
                    progress.advance(task_n)

            for i in range(num_batches):
                mapped_all.extend(results_by_batch.get(i, []))
            progress.finish(task_n)

        # QA mapping
        qa_mapped_ids: set[str] = set()
        if qa_blocks:
            total_q = len(qa_blocks)
            batch_size_q = self._choose_batch_size(total_q, map_batch_override)
            num_batches_q = math.ceil(total_q / batch_size_q)
            batches_q = [(i // batch_size_q, qa_blocks[i:i+batch_size_q]) for i in range(0, total_q, batch_size_q)]
            task_q = progress.start(
                f"Mapping Q&A (≈{batch_size_q}, {num_batches_q} batches)", total=num_batches_q
            )

            def run_batch_qa(payload: Tuple[int, List[Dict]]):
                bidx, items = payload
                chain = self._make_chain_qa()
                mapped = self.retryer.call(chain.invoke, ctx.final_tree, items, config={"meta": f"map:qa:{bidx+1}/{num_batches_q}"})
                mapped = [m for m in mapped if m.get("element_id") and m.get("target_node_id")]
                return (bidx, mapped)

            results_by_batch_q: Dict[int, List[Dict]] = {}
            with executor.get() as pool:
                futs = {pool.submit(run_batch_qa, item): item[0] for item in batches_q}
                for fut in as_completed(futs):
                    bidx, mapped = fut.result()
                    results_by_batch_q[bidx] = mapped
                    progress.advance(task_q)

            for i in range(num_batches_q):
                mapped_all.extend(results_by_batch_q.get(i, []))
                for m in results_by_batch_q.get(i, []):
                    if m.get("element_id"):
                        qa_mapped_ids.add(m["element_id"])
            progress.finish(task_q)

            # coverage + unmapped reporting
            all_qa_ids = {b["element_id"] for b in qa_blocks if b.get("element_id")}
            unmapped = sorted(all_qa_ids - qa_mapped_ids)
            store.save_debug("map_qa_coverage.json", {
                "total_questions": len(all_qa_ids),
                "mapped": len(qa_mapped_ids),
                "unmapped": len(unmapped),
                "coverage_pct": (len(qa_mapped_ids) / len(all_qa_ids) * 100.0) if all_qa_ids else 100.0,
            })
            store.save_debug("map_unmapped_qa.json", [{"element_id": eid} for eid in unmapped])

        if not mapped_all:
            store.save_debug(self.FINAL_TREE_ARTIFACT, ctx.final_tree)
            return ctx

        # de-dup
        deduped, seen_ids = [], set()
        for m in mapped_all:
            if m["element_id"] in seen_ids:
                continue
            seen_ids.add(m["element_id"])
            deduped.append(m)

        # enrich markdown for non-QA refs
        id_to_block: Dict[str, Dict] = {}
        for ch in ctx.chunks:
            for b in ch.get("blocks", []):
                if eid := b.get("element_id"):
                    id_to_block[eid] = b
        for b in getattr(ctx, "qa_blocks", []) or []:
            if eid := b.get("element_id"):
                id_to_block[eid] = b

        task_enrich = progress.start("Enriching mapped refs", total=len(deduped))
        for m in deduped:
            b = id_to_block.get(m["element_id"])
            if not b:
                progress.advance(task_enrich)
                continue
            btype = (b.get("type") or "").lower()
            if btype == "qa":
                # keep Q + A in the final content_refs, even if mapping used only Q
                m["q"] = b.get("q") or ""
                m["a"] = b.get("a") or ""
                m["type"] = "qa"
                m["markdown"] = ""
            elif btype == "code":
                m["markdown"] = b.get("markdown") or f"```{b.get('language','')}\n{b.get('text','')}\n```"
            elif btype == "table":
                m["markdown"] = b.get("text", "") or ""
            elif btype == "image":
                alt = (b.get("alt") or "image").strip()
                src = b.get("src", "") or ""
                m["markdown"] = f"![{alt}]({src})"
            else:
                m["markdown"] = b.get("markdown") or b.get("text") or ""
            progress.advance(task_enrich)
        progress.finish(task_enrich)

        store.save_debug("map_mapped_final.json", deduped)
        insert_content_refs_into_tree(ctx.final_tree, deduped)
        store.save_debug(self.FINAL_TREE_ARTIFACT, ctx.final_tree)
        return ctx
