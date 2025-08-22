# FILE: mark2mind/pipeline/runner.py
from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, Any, List
from rich.console import Console
from datetime import datetime
import uuid

from mark2mind import __version__
from mark2mind.utils.tree_helper import add_order_and_fingerprint

from mark2mind.pipeline.stages.clean_for_map import CleanForMapStage
from mark2mind.pipeline.stages.reformat import ReformatTextStage
from mark2mind.pipeline.stages.subtitles import SubtitlesListStage, SubtitlesMergeStage

from .core.config import RunConfig
from .core.context import RunContext
from .core.artifacts import ArtifactStore
from .core.progress import RichProgressReporter
from .core.retry import Retryer
from .core.llm_pool import LLMFactoryPool
from .core.executor_provider import ExecutorProvider
from .stages import (
    ChunkStage,
    QAStage,
    TreeStage,
    ClusterStage,
    MergeStage,
    RefineStage,
    MapContentStage,
    QAFromMarkdownStage,
)
from .export import MarkdownExporter, JSONExporter

from mark2mind.chains.generate_tree_chain import ChunkTreeChain
from mark2mind.chains.merge_tree_chain import TreeMergeChain
from mark2mind.chains.refine_tree_chain import TreeRefineChain
from mark2mind.chains.map_content_mindmap_chain import ContentMappingChain
from mark2mind.chains.generate_questions_chain import GenerateQuestionsChain
from mark2mind.chains.answer_questions_chain import AnswerQuestionsChain
from mark2mind.pipeline.stages.bullets import BulletsStage

class StepRunner:
    def __init__(
        self,
        config: RunConfig,
        *,
        debug: bool = False,
        callbacks=None,
        llm_factory=None,
        chunk_chain: Optional[ChunkTreeChain] = None,
        merge_chain: Optional[TreeMergeChain] = None,
        refine_chain: Optional[TreeRefineChain] = None,
        content_chain: Optional[ContentMappingChain] = None,
        qa_question_chain: Optional[GenerateQuestionsChain] = None,
        qa_answer_chain: Optional[AnswerQuestionsChain] = None,
        console: Optional[Console] = None,
    ):
        self.cfg = config
        self.console = console or Console()
        self.callbacks = callbacks
        self.debug = debug

        self.store = ArtifactStore(
            debug_root=config.debug_root,
            output_root=config.output_root,
            run_name=config.run_name,
            enable_debug=self.debug
        )
        self.retryer = Retryer(max_retries=config.max_retries, min_delay_sec=config.min_delay_sec)
        self.llm_pool = LLMFactoryPool(llm_factory)
        self.executor = ExecutorProvider(max_workers=config.executor_max_workers)

        app = config.app
        if app:
            os_env = __import__("os").environ
            os_env["MARK2MIND_CHUNK_OVERLAP_TOKENS"] = str(app.chunk.overlap_tokens)
            os_env["MARK2MIND_MIN_DELAY_SEC"] = str(app.runtime.min_delay_sec)
            os_env["MARK2MIND_MAX_RETRIES"] = str(app.runtime.max_retries)
            if app.runtime.map_batch_override is not None:
                os_env["MARK2MIND_MAP_BATCH"] = str(app.runtime.map_batch_override)
            os_env.setdefault("MARK2MIND_ID_SCOPE", "content")

        # Stages
        self.chunk_stage = ChunkStage()
        self.qa_stage = QAStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.tree_stage = TreeStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.cluster_stage = ClusterStage()
        self.merge_stage = MergeStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.refine_stage = RefineStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.map_stage = MapContentStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.bullets_stage = BulletsStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.reformat_text_stage = ReformatTextStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.clean_for_map_stage = CleanForMapStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.subs_list_stage = SubtitlesListStage()
        self.subs_merge_stage = SubtitlesMergeStage()
        self.qa_from_md_stage = QAFromMarkdownStage()

        self.md_exporter = MarkdownExporter()
        self.json_exporter = JSONExporter()

    def _ensure_file_mode(self):
        if self.cfg.is_dir_mode:
            raise RuntimeError(
                "Flow error: file-based pipeline selected but [io].input points to a directory.\n"
                "Fix: set [pipeline] to a subtitles preset (subs_list/subs_merge) or point [io].input to a Markdown file."
            )

    def _ensure_dir_mode(self):
        if not self.cfg.is_dir_mode:
            raise RuntimeError(
                "Flow error: subtitles pipeline selected but [io].input points to a file.\n"
                "Fix: set [io].input to the directory containing your subtitles."
            )

    def run(self):
        app = self.cfg.app
        with RichProgressReporter(self.console) as progress:

            # ---- SUBTITLES FLOWS -------------------------------------------------
            if "subs_list" in self.cfg.steps or "subs_merge" in self.cfg.steps:
                self._ensure_dir_mode()
                manifest_rel = app.io.manifest
                manifest_path = self.store.resolve_workspace_path(manifest_rel) \
                    if not Path(manifest_rel).is_absolute() else Path(manifest_rel)

                if "subs_list" in self.cfg.steps:
                    self.subs_list_stage.run(
                        RunContext(text=""),
                        self.store,
                        progress,
                        list_dir=str(self.cfg.input_path),
                        manifest_path=str(manifest_path),
                        enable_html=bool(app.io.include_html),
                    )
                    return

                if "subs_merge" in self.cfg.steps:
                    if not manifest_path.exists():
                        raise FileNotFoundError(
                            f"Missing manifest for subs_merge: {manifest_path}\n"
                            "Hint: run 'subs_list' first, or set [io].manifest to an existing manifest file."
                        )
                    merged_out_rel = "subtitles_merged.md"
                    merged_out_path = self.store.resolve_workspace_path(merged_out_rel)
                    self.subs_merge_stage.run(
                        RunContext(text=""),
                        self.store,
                        progress,
                        manifest_path=str(manifest_path),
                        output_md=str(merged_out_path),
                        enable_html=bool(app.io.include_html),
                    )
                    return

            # File-based pipelines
            self._ensure_file_mode()
            text = self.cfg.input_path.read_text(encoding="utf-8")
            ctx = RunContext(text=text)

            if "chunk" in self.cfg.steps:
                ctx = self.chunk_stage.run(
                    ctx,
                    app.chunk.max_tokens,
                    self.store,
                    progress,
                    debug=self.debug,
                    use_debug_io=self.cfg.use_debug_io,
                )
            elif self.cfg.use_debug_io:
                loaded = self.store.load_debug("chunks.json")
                if loaded is not None:
                    ctx.chunks = loaded

            if "reformat" in self.cfg.steps:
                ctx = self.reformat_text_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )
                self.md_exporter.export_bullets(getattr(ctx, "reformat_outputs", []),
                    self.store.resolve_workspace_path("reformatted.md"))
                self.console.log(f"✅ reformatted markdown saved to: {self.store.resolve_workspace_path('reformatted.md')}")

            if "clean_for_map" in self.cfg.steps:
                ctx = self.clean_for_map_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )
                self.md_exporter.export_bullets(getattr(ctx, "clean_for_map_outputs", []),
                    self.store.resolve_workspace_path("clean_for_map.md"))
                self.console.log(f"✅ reformatted markdown saved to: {self.store.resolve_workspace_path('clean_for_map.md')}")

            if "bullets" in self.cfg.steps:
                ctx = self.bullets_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )
                self.md_exporter.export_bullets(getattr(ctx, "bullets_outputs", []),
                    self.store.resolve_workspace_path("bullets.md"))
                self.console.log(f"✅ Bulleted markdown saved to: {self.store.resolve_workspace_path('bullets.md')}")

            if "qa" in self.cfg.steps:
                ctx = self.qa_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )
                self.md_exporter.export_qa(
                    ctx.chunks, self.store.resolve_workspace_path("qa.md")
                )
            elif self.cfg.use_debug_io:
                loaded = self.store.load_debug("chunks_with_qa.json")
                if loaded is not None:
                    ctx.chunks = loaded

            if "tree" in self.cfg.steps:
                ctx = self.tree_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )
            if "cluster" in self.cfg.steps:
                ctx = self.cluster_stage.run(
                    ctx,
                    self.store,
                    progress,
                    use_debug_io=self.cfg.use_debug_io,
                )
            if "merge" in self.cfg.steps:
                ctx = self.merge_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )
            if "refine" in self.cfg.steps:
                ctx = self.refine_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                )

            # NEW: parse QA markdown before mapping (if requested)
            if "qa_parse" in self.cfg.steps:
                ctx = self.qa_from_md_stage.run(
                    ctx,
                    self.store,
                    progress,
                    use_debug_io=self.cfg.use_debug_io,
                )

            if "map" in self.cfg.steps:
                ctx = self.map_stage.run(
                    ctx,
                    self.store,
                    progress,
                    executor=self.executor,
                    use_debug_io=self.cfg.use_debug_io,
                    map_batch_override=self.cfg.map_batch_override,
                )

                if ctx.final_tree:
                    # aggregate tags from chunk results
                    tag_set = {t for r in ctx.chunk_results for t in r.get("tags", [])}

                    # annotate nodes with order + fingerprint
                    add_order_and_fingerprint(ctx.final_tree)

                    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                    ctx.final_tree.update({
                        "schema_version": "1.0.0",
                        "map_id": str(uuid.uuid4()),
                        "meta": {
                            "created_at": now,
                            "updated_at": now,
                            "revision": 1,
                            "source": str(self.cfg.input_path),
                            "generator": {
                                "name": "mark2mind",
                                "version": __version__,
                                "run_id": self.cfg.run_id,
                            },
                        },
                        "tags": sorted(tag_set),
                    })

                    # Filenames based on run_name (e.g., intro → intro.*)
                    from mark2mind.utils.exporters import to_camel_nospace
                    base_name = to_camel_nospace(self.cfg.run_name)
                    json_out_path = self.store.resolve_workspace_path(f"{base_name}.mindmap.json")
                    markmap_out_path = self.store.resolve_workspace_path(f"{base_name}.markmap.md")
                    pages_dir = self.store.resolve_workspace_path(base_name)


                    # Ensure final_tree.json in DEBUG matches the exported JSON (identical content)
                    self.store.save_debug("final_tree.json", ctx.final_tree)

                    # Export final tree JSON
                    self.json_exporter.export_mindmap(ctx.final_tree, json_out_path)
                    self.console.log(f"✅ Mindmap (final) saved to: {json_out_path}")

                    # Export markmap with Obsidian-friendly links + material pages per node
                    self.md_exporter.export_markmap_with_node_pages(
                        tree=ctx.final_tree,
                        out_md_path=markmap_out_path,
                        pages_dir=pages_dir,
                        link_folder_name=base_name,
                    )
                    self.console.log(f"✅ Markmap markdown saved to: {markmap_out_path}")

                    # Any “no-refs” or auxiliary variants go into DEBUG only
                    def _strip_content_refs(node: Dict[str, Any]) -> Dict[str, Any]:
                        clean = {k: v for k, v in node.items() if k != "content_refs"}
                        children = clean.get("children") or []
                        clean["children"] = [_strip_content_refs(c) for c in children]
                        return clean
                    from copy import deepcopy
                    stripped = _strip_content_refs(deepcopy(ctx.final_tree))
                    self.store.save_debug("mindmap.norefs.json", stripped)
