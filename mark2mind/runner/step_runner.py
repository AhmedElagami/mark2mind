import json
from pathlib import Path
from typing import List, Dict
import os
import random
import threading

from mark2mind.chains.generate_tree_chain import ChunkTreeChain
from mark2mind.chains.merge_tree_chain import TreeMergeChain
from mark2mind.chains.refine_tree_chain import TreeRefineChain
from mark2mind.chains.map_content_mindmap_chain import ContentMappingChain
from mark2mind.chains.generate_questions_chain import GenerateQuestionsChain
from mark2mind.chains.answer_questions_chain import AnswerQuestionsChain

from mark2mind.utils.clustering import cluster_chunk_trees
from mark2mind.utils.tree_helper import assign_node_ids, insert_content_refs_into_tree
from mark2mind.utils.debug import write_debug_file
from mark2mind.utils.chunker import chunk_markdown

from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, BarColumn, TextColumn,
    MofNCompleteColumn, TimeElapsedColumn, TimeRemainingColumn
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from mark2mind.utils.executor import get_executor




class StepRunner:
    def __init__(
        self,
        input_file: str,
        file_id: str,
        steps: List[str],
        debug: bool,
        chunk_chain: ChunkTreeChain,
        merge_chain: TreeMergeChain,
        refine_chain: TreeRefineChain,
        content_chain: ContentMappingChain,
        qa_question_chain: GenerateQuestionsChain,
        qa_answer_chain: AnswerQuestionsChain,
        callbacks = None,
        debug_dir: str = "debug",
        output_dir: str = "output",
        force: bool = False,
        run_id: str | None = None,
        llm_factory = None,
        executor=None
    ):
        self.llm_factory = llm_factory
        self.min_delay_sec = float(os.getenv("MARK2MIND_MIN_DELAY_SEC", "0.15"))  # spacing between requests in a thread
        self.max_retries = int(os.getenv("MARK2MIND_MAX_RETRIES", "4"))

        self._thread_local = threading.local()
        self._last_call_ts = threading.local()
        self.executor = executor or get_executor()


        self.file_id = file_id
        self.steps = steps
        self.debug = debug
        self.chunk_chain = chunk_chain
        self.merge_chain = merge_chain
        self.refine_chain = refine_chain
        self.content_chain = content_chain
        self.qa_question_chain = qa_question_chain
        self.qa_answer_chain = qa_answer_chain
        self.force = force

        self.input_file = Path(input_file)
        self.debug_dir = Path(debug_dir) / file_id
        self.output_dir = Path(output_dir)
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        self.text = self.input_file.read_text(encoding="utf-8")
        self.chunks: List[Dict] = []
        self.chunk_results: List[Dict] = []
        self.final_tree: Dict = {}
        self.callbacks = callbacks

        self.run_id = run_id or "manual"

        self.console = Console()
        self.progress = None

    def _cfg(self, *, step: str, klass: str, **extras_tags):
        base_tags = [f"run:{self.run_id}", f"file:{self.file_id}", f"step:{step}", f"class:{klass}"]
        # extras_tags can be like {"chunk": idx, "cluster": cid}
        for k, v in extras_tags.items():
            base_tags.append(f"{k}:{v}")
        return {
            "tags": base_tags,
            "metadata": {
                "run_id": self.run_id,
                "file_id": self.file_id,
                "step": step,
                "class": klass,
                **extras_tags
            }
        }

    def run(self):
        # A single progress UI for the whole run
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,                # keep the bars after finishing; set True if you prefer them to disappear
            console=self.console,
        ) as progress:
            self.progress = progress

            if "chunk" in self.steps:
                self.chunk()
            else:
                self._load_if_exists("chunks.json", attr="chunks")

            if "qa" in self.steps:
                self.generate_qa()
                from mark2mind.utils.exporters import export_qa_nested_headers
                qa_md = self.output_dir / f"{self.file_id}_qa.md"
                qa_md.parent.mkdir(parents=True, exist_ok=True)
                export_qa_nested_headers(self.chunks, str(qa_md))
            else:
                self._load_if_exists("chunks_with_qa.json", attr="chunks")

            if "tree" in self.steps:
                self.generate_trees()

            if "cluster" in self.steps:
                self.cluster_chunks()

            if "merge" in self.steps:
                self.merge_clusters()

            if "refine" in self.steps:
                self.refine_tree()

            if "map" in self.steps:
                self.map_content()

            if self.final_tree:
                out_path = self.output_dir / f"{self.file_id}_mindmap.json"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(json.dumps(self.final_tree, indent=2, ensure_ascii=False), encoding="utf-8")
                self.console.log(f"✅ Mindmap saved to: {out_path}")

                try:
                    from mark2mind.utils.exporters import export_tree_as_markmap_md
                    mm_md = self.output_dir / f"{self.file_id}_mindmap.markmap.md"
                    export_tree_as_markmap_md(self.final_tree, str(mm_md))
                except Exception as e:
                    self.console.log(f"⚠️ Markmap export failed: {e}")

            self.progress = None


    def chunk(self):
        self.console.log("🔍 Chunking markdown...")
        self.chunks = chunk_markdown(self.text, max_tokens=1024, debug=self.debug, debug_dir=self.debug_dir)
        write_debug_file(self.debug_dir / "chunks.json", self.chunks)

    def generate_qa(self):
        self.console.log("🧠 Generating Q&A...")

        def add_qa(idx_chunk):
            idx, chunk = idx_chunk
            chains = self._make_chains()
            cfg_q = self._cfg(step="qa", klass="GenerateQuestionsChain", chunk=idx)
            questions = self._with_retry(chains["qa_q"].invoke, chunk, config=cfg_q)

            cfg_a = self._cfg(step="qa", klass="AnswerQuestionsChain", chunk=idx)
            answers = self._with_retry(chains["qa_a"].invoke, chunk, questions, config=cfg_a)

            id_map = {b["element_id"]: b for b in chunk["blocks"]}
            for b in chunk["blocks"]:
                b["qa_pairs"] = []
            for qa in answers:
                if (eid := qa.get("element_id")) in id_map:
                    id_map[eid]["qa_pairs"].append(qa)
            return idx, chunk

        items = list(enumerate(self.chunks))
        task_id = self.progress.add_task("Q&A per chunk", total=len(items))

        futures = {self.executor.submit(add_qa, item): item for item in items}
        updated = []
        for fut in as_completed(futures):
            updated.append(fut.result())
            self.progress.advance(task_id)

        self.chunks = [chunk for _, chunk in sorted(updated)]
        write_debug_file(self.debug_dir / "chunks_with_qa.json", self.chunks)



    def generate_trees(self):
        self.console.log("🌲 Generating semantic trees...")

        def chunk_heading_summary(chunk):
            from collections import Counter
            c = Counter()
            for b in chunk.get("blocks", []):
                path = " › ".join(b.get("heading_path") or [])
                c[path] += int(b.get("token_count", 0)) or 1
            return [p for p,_ in c.most_common(3)]

        def process(idx_chunk):
            idx, chunk = idx_chunk
            chains = self._make_chains()
            cfg = self._cfg(step="tree", klass="ChunkTreeChain", chunk=idx)
            out = self._with_retry(chains["chunk"].invoke, chunk, config=cfg)
            return {
                **out,
                "metadata": {
                    **chunk.get("metadata", {}),
                    "heading_paths_top": chunk_heading_summary(chunk),
                }
            }

        items = list(enumerate(self.chunks))
        task_id = self.progress.add_task("Trees per chunk", total=len(items))

        futures = {self.executor.submit(process, item): item for item in items}
        results = []
        for fut in as_completed(futures):
            results.append(fut.result())
            self.progress.advance(task_id)

        self.chunk_results = results
        write_debug_file(self.debug_dir / "chunk_trees.json", self.chunk_results)



    def cluster_chunks(self):
        self.console.log("🧠 Clustering chunks...")
        n = len(self.chunk_results)
        if n <= 1:
            self.clustered = [self.chunk_results]
            return
        self.clustered = cluster_chunk_trees(self.chunk_results, None)
        write_debug_file(self.debug_dir / "clusters.json", self.clustered)


    def merge_clusters(self):
        self.console.log("🔗 Merging trees within clusters...")

        def merge_group(payload):
            cid, group = payload
            chains = self._make_chains()
            trees = [i["tree"] for i in group if i["tree"]]

            round_idx = 0
            while len(trees) > 1:
                pairs = [(trees[i], trees[i + 1]) for i in range(0, len(trees) - 1, 2)]
                leftovers = [trees[-1]] if len(trees) % 2 == 1 else []

                def merge_pair(j_ab):
                    j, (a, b) = j_ab
                    cfg = self._cfg(step="merge", klass="TreeMergeChain", cluster=cid, pair=f"{round_idx}:{j}")
                    return self._with_retry(chains["merge"].invoke, a, b, config=cfg)

                if pairs:
                    # submit and collect in ORIGINAL pair order
                    fut_map = {self.executor.submit(merge_pair, (j, ab)): j for j, ab in enumerate(pairs)}
                    merged_by_idx = {}
                    for f in as_completed(fut_map):
                        j = fut_map[f]
                        merged_by_idx[j] = f.result()
                    merged = [merged_by_idx[j] for j in range(len(pairs))]
                else:
                    merged = []

                trees = merged + leftovers
                round_idx += 1

            return trees[0] if trees else None

        items = list(enumerate(self.clustered))
        task_id = self.progress.add_task("Merging clusters", total=len(items))

        futures = {self.executor.submit(merge_group, item): item for item in items}
        trees = []
        for fut in as_completed(futures):
            trees.append(fut.result())
            self.progress.advance(task_id)

        self.cluster_trees = [t for t in trees if t]
        write_debug_file(self.debug_dir / "merged_clusters.json", self.cluster_trees)


    def refine_tree(self):
        self.console.log("🧹 Refining final tree")

        if not getattr(self, "cluster_trees", None):
            self.console.log("⚠️ No cluster trees to refine.")
            return

        chains = self._make_chains()
        task_id = self.progress.add_task("Refining", total=2)

        def merge_all_parallel(trees):
            cur = [t for t in trees if t]
            if not cur:
                return None

            round_idx = 0
            while len(cur) > 1:
                pairs = [(cur[i], cur[i + 1]) for i in range(0, len(cur) - 1, 2)]
                leftovers = [cur[-1]] if len(cur) % 2 == 1 else []

                def merge_pair(j_ab):
                    j, (a, b) = j_ab
                    cfg = self._cfg(step="merge", klass="TreeMergeChain", pair=f"refine:{round_idx}:{j}")
                    return self._with_retry(chains["merge"].invoke, a, b, config=cfg)

                if pairs:
                    # submit and collect in ORIGINAL pair order
                    fut_map = {self.executor.submit(merge_pair, (j, ab)): j for j, ab in enumerate(pairs)}
                    merged_by_idx = {}
                    for f in as_completed(fut_map):
                        j = fut_map[f]
                        merged_by_idx[j] = f.result()
                    merged = [merged_by_idx[j] for j in range(len(pairs))]
                else:
                    merged = []

                cur = merged + leftovers
                round_idx += 1

            return cur[0]

        # 1) Merge all cluster trees
        merged = merge_all_parallel(self.cluster_trees)
        self.progress.advance(task_id)
        if not merged:
            self.console.log("⚠️ Nothing to refine after merging.")
            return

        # 2) Refine once
        refined = self._with_retry(chains["refine"].invoke, merged)
        self.progress.advance(task_id)

        # 3) Finalize
        assign_node_ids(refined)
        self.final_tree = refined
        write_debug_file(self.debug_dir / "refined_tree.json", refined)



    def map_content(self):
        """
        Map all unique content blocks to the final tree in batched, (now) parallel fashion.
        - Dedup by element_id (removes overlap duplicates)
        - Auto-pick batch size based on total blocks (env override available)
        - Run mapper batches concurrently with thread-safe LLM usage
        - Insert into the tree once (no threading races)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import os, math

        log = getattr(self, "console", None)
        (log.log("📎 Mapping content to final tree...") if log else print("📎 Mapping content to final tree..."))

        if not getattr(self, "final_tree", None):
            (log.log("⚠️ No final_tree available; skipping mapping.")
            if log else print("⚠️ No final_tree available; skipping mapping."))
            return

        # 1) Collect unique, supported blocks across all chunks
        supported_types = {"paragraph", "code", "table", "image"}
        seen_ids = set()
        unique_blocks = []

        def mk_caption(b):
            # best-effort short caption for the mapper prompt
            if b.get("type") == "image":
                return (b.get("alt") or "Image").strip()[:80]
            txt = (b.get("text") or b.get("markdown") or "").strip()
            if txt:
                return txt.splitlines()[0][:80]
            hp = b.get("heading_path") or []
            return " / ".join(hp[-2:])[:80] if hp else "Content block"

        for ch in self.chunks:
            for b in ch.get("blocks", []):
                eid = b.get("element_id")
                if not eid or eid in seen_ids:
                    continue
                if b.get("type") not in supported_types:
                    continue
                seen_ids.add(eid)
                # keep only what the mapping prompt needs
                block = {
                    "element_id": eid,
                    "type": b["type"],
                    "element_caption": b.get("element_caption") or mk_caption(b),
                    "markdown": b.get("markdown") or b.get("text") or b.get("src") or "",
                    "is_atomic": b.get("is_atomic", False),
                }
                unique_blocks.append(block)

        if not unique_blocks:
            (log.log("ℹ️ No eligible content blocks to map.")
            if log else print("ℹ️ No eligible content blocks to map."))
            return

        total = len(unique_blocks)

        # 2) Decide batch size
        # If MARK2MIND_MAP_BATCH is a number, use it. Otherwise, pick based on total:
        # - Aim for ~6–10 batches to balance token duplication of the tree vs. batch size.
        # - Clamp batch size to [20, 80] unless overridden.
        def _choose_batch_size(n: int) -> int:
            env_val = os.getenv("MARK2MIND_MAP_BATCH", "").strip().lower()
            if env_val.isdigit():
                return max(1, int(env_val))

            # Auto mode
            target_batches = min(max(6, round(n / 60)), 10)  # ~60 blocks per batch, 6–10 batches cap
            batch = max(1, math.ceil(n / max(1, target_batches)))
            # Clamp for safety (you can tweak these bounds)
            return max(20, min(80, batch)) if n >= 20 else n

        batch_size = _choose_batch_size(total)
        num_batches = math.ceil(total / batch_size)

        # 3) Progress handling
        maybe_external_progress = getattr(self, "progress", None)
        if maybe_external_progress is not None:
            progress_cm = maybe_external_progress
            created_progress_here = False
        else:
            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn, TimeRemainingColumn
            progress_cm = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                transient=False,
                console=getattr(self, "console", None)
            )
            progress_cm.__enter__()
            created_progress_here = True

        # 4) Build batches
        batches = []
        for i in range(0, total, batch_size):
            batches.append((i // batch_size, unique_blocks[i:i + batch_size]))  # (batch_idx, batch_items)

        # 5) Run batches in parallel
        all_mapped = []
        try:
            task_batches = progress_cm.add_task(
                f"Mapping content batches (size≈{batch_size}, {num_batches} batches)",
                total=num_batches
            )

            # Worker uses thread-local LLM + retry wrapper
            def _run_batch(batch_idx_and_items):
                bidx, batch_items = batch_idx_and_items
                # Build thread-local chains (VERY important for thread safety)
                chains = self._make_chains()
                cfg = self._cfg(
                    step="map",
                    klass="ContentMappingChain",
                    batch=f"{bidx + 1}/{num_batches}",
                )
                mapped = self._with_retry(chains["content"].invoke, self.final_tree, batch_items, config=cfg)
                # Defensive filter
                mapped = [m for m in mapped if m.get("element_id") and m.get("target_node_id")]
                return (bidx, mapped)

            # Parallel execution
            results_by_batch = {}
            futures = {self.executor.submit(_run_batch, item): item[0] for item in batches}
            for fut in as_completed(futures):
                bidx, mapped = fut.result()
                results_by_batch[bidx] = mapped
                progress_cm.advance(task_batches)

            # Preserve ascending batch order when concatenating
            for bidx in sorted(results_by_batch.keys()):
                all_mapped.extend(results_by_batch[bidx])

            # 6) Deduplicate mapped refs by element_id (keep first)
            deduped = []
            seen_map = set()
            for m in all_mapped:
                if m["element_id"] in seen_map:
                    continue
                seen_map.add(m["element_id"])
                deduped.append(m)

            # 7) Enrichment (single-threaded)
            # Build lookup before enrichment
            id_to_block = {}
            for ch in self.chunks:
                for b in ch.get("blocks", []):
                    if b.get("element_id"):
                        id_to_block[b["element_id"]] = b

            task_enrich = progress_cm.add_task("Enriching mapped refs", total=len(deduped))

            for m in deduped:
                b = id_to_block.get(m["element_id"])
                if b:
                    btype = b.get("type")
                    if btype == "code":
                        m["markdown"] = b.get("markdown") or f"```{b.get('language','')}\n{b.get('text','')}\n```"
                    elif btype == "table":
                        m["markdown"] = b.get("text", "") or ""
                    elif btype == "image":
                        alt = (b.get("alt") or m.get("element_caption") or "image").strip()
                        src = b.get("src", "") or ""
                        m["markdown"] = f"![{alt}]({src})"
                    else:  # paragraph (or fallback)
                        m["markdown"] = b.get("markdown") or b.get("text") or ""
                progress_cm.advance(task_enrich)

            # 8) Single mutation point (no lock needed)
            insert_content_refs_into_tree(self.final_tree, deduped)
            write_debug_file(self.debug_dir / "final_tree.json", self.final_tree)

            (log.log(f"✅ Mapped {len(deduped)} content blocks into the tree using {num_batches} batch(es) @ ~{batch_size}/batch.")
            if log else print(f"✅ Mapped {len(deduped)} content blocks into the tree using {num_batches} batch(es) @ ~{batch_size}/batch."))

        finally:
            if created_progress_here:
                progress_cm.__exit__(None, None, None)

    def _load_if_exists(self, filename: str, attr: str):
        path = self.debug_dir / filename
        if not self.force and path.exists():
            with open(path, "r", encoding="utf-8") as f:
                setattr(self, attr, json.load(f))

    def _get_thread_llm(self):
        """
        Create one LLM client per thread to avoid thread-safety issues.
        Falls back to the shared llm on construction if no factory provided.
        """
        if getattr(self._thread_local, "llm", None) is None:
            if self.llm_factory is not None:
                self._thread_local.llm = self.llm_factory()
            else:
                # Fallback: use the already-bound LLM from the chain (not ideal for heavy parallelism)
                self._thread_local.llm = None
        return self._thread_local.llm

    def _make_chains(self):
        """
        Build fresh chain instances bound to the thread-local LLM.
        This avoids sharing a single chain/LLM across threads.
        """
        llm = self._get_thread_llm()
        # If no factory was provided, we reuse the prebuilt chains (serial-safe path).
        if llm is None:
            return {
                "chunk": self.chunk_chain,
                "merge": self.merge_chain,
                "refine": self.refine_chain,
                "content": self.content_chain,
                "qa_q": self.qa_question_chain,
                "qa_a": self.qa_answer_chain,
            }
        from mark2mind.chains.generate_tree_chain import ChunkTreeChain
        from mark2mind.chains.merge_tree_chain import TreeMergeChain
        from mark2mind.chains.refine_tree_chain import TreeRefineChain
        from mark2mind.chains.map_content_mindmap_chain import ContentMappingChain
        from mark2mind.chains.generate_questions_chain import GenerateQuestionsChain
        from mark2mind.chains.answer_questions_chain import AnswerQuestionsChain

        return {
            "chunk": ChunkTreeChain(llm, callbacks=self.callbacks),
            "merge": TreeMergeChain(llm, callbacks=self.callbacks),
            "refine": TreeRefineChain(llm, callbacks=self.callbacks),
            "content": ContentMappingChain(llm, callbacks=self.callbacks),
            "qa_q": GenerateQuestionsChain(llm, callbacks=self.callbacks),
            "qa_a": AnswerQuestionsChain(llm, callbacks=self.callbacks),
        }

    def _rate_limit_pause(self):
        # lightweight inter-call spacing per thread
        import time
        now = time.time()
        last = getattr(self._last_call_ts, "t", 0.0)
        dt = now - last
        if dt < self.min_delay_sec:
            time.sleep(self.min_delay_sec - dt + random.uniform(0, 0.05))
        self._last_call_ts.t = time.time()

    def _with_retry(self, fn, *args, **kwargs):
        import time, random
        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit_pause()
                return fn(*args, **kwargs)
            except Exception:
                if attempt == self.max_retries:
                    raise
                backoff = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.25)
                time.sleep(backoff)
