from __future__ import annotations

from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.console import Console

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
from .stages import ChunkStage, QAStage, TreeStage, ClusterStage, MergeStage, RefineStage, MapContentStage
from .export import MarkdownExporter, JSONExporter

from mark2mind.chains.generate_tree_chain import ChunkTreeChain
from mark2mind.chains.merge_tree_chain import TreeMergeChain
from mark2mind.chains.refine_tree_chain import TreeRefineChain
from mark2mind.chains.map_content_mindmap_chain import ContentMappingChain
from mark2mind.chains.generate_questions_chain import GenerateQuestionsChain
from mark2mind.chains.answer_questions_chain import AnswerQuestionsChain
from mark2mind.pipeline.stages.bullets import BulletsStage


class StepRunner:
    """
    WHAT changed (v2-min):
    - Uses ArtifactStore(run_name=...) with workspace auto-naming.
    - Infers mode from cfg.is_dir_mode (file vs directory).
    - Auto names outputs:
        * chunks, qa, mindmap, bullets, etc:
            output/<run_name>/mindmap.json
            output/<run_name>/mindmap.markmap.md
            output/<run_name>/qa.md
            output/<run_name>/bullets.md
        * subtitles manifest/merge:
            output/<run_name>/<manifest> (relative path resolved into workspace)
            output/<run_name>/subtitles_merged.md (default)
    - Clear user-facing errors for wrong flows.
    """

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

        # Workspace (auto-naming)
        self.store = ArtifactStore(
            debug_root=config.debug_root,
            output_root=config.output_root,
            run_name=config.run_name,
        )

        self.retryer = Retryer(max_retries=config.max_retries, min_delay_sec=config.min_delay_sec)
        self.llm_pool = LLMFactoryPool(llm_factory)
        self.executor = ExecutorProvider(max_workers=config.executor_max_workers)

        app = config.app
        if app:
            # Env shims for utilities
            os_env = __import__("os").environ
            os_env["MARK2MIND_CHUNK_OVERLAP_TOKENS"] = str(app.chunk.overlap_tokens)
            os_env["MARK2MIND_MIN_DELAY_SEC"] = str(app.runtime.min_delay_sec)
            os_env["MARK2MIND_MAX_RETRIES"] = str(app.runtime.max_retries)
            if app.runtime.map_batch_override is not None:
                os_env["MARK2MIND_MAP_BATCH"] = str(app.runtime.map_batch_override)
            os_env.setdefault("MARK2MIND_ID_SCOPE", "content")

        # Stages
        self.chunk_stage = ChunkStage()
        self.qa_stage = QAStage(self.llm_pool, self.retryer, callbacks=callbacks,
                                chain_instances={"qa_q": qa_question_chain, "qa_a": qa_answer_chain})
        self.tree_stage = TreeStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instance=chunk_chain)
        self.cluster_stage = ClusterStage()
        self.merge_stage = MergeStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instance=merge_chain)
        self.refine_stage = RefineStage(self.llm_pool, self.retryer, callbacks=callbacks,
                                        merge_chain_instance=merge_chain, refine_chain_instance=refine_chain)
        self.map_stage = MapContentStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instance=content_chain)
        self.bullets_stage = BulletsStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.reformat_text_stage = ReformatTextStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.clean_for_map_stage = CleanForMapStage(self.llm_pool, self.retryer, callbacks=callbacks)
        self.subs_list_stage = SubtitlesListStage()
        self.subs_merge_stage = SubtitlesMergeStage()

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
                # Resolve manifest location:
                # - if relative → inside workspace (output/<run_name>/...)
                manifest_rel = app.io.manifest
                manifest_path = self.store.resolve_workspace_path(manifest_rel) \
                    if not Path(manifest_rel).is_absolute() else Path(manifest_rel)

                if "subs_list" in self.cfg.steps:
                    # List all matching subtitle files into a manifest in the workspace
                    self.subs_list_stage.run(
                        RunContext(text=""),
                        self.store,
                        progress,
                        list_dir=str(self.cfg.input_path),
                        manifest_path=str(manifest_path),
                        enable_html=bool(app.io.include_html),
                    )
                    # Early return for pure listing
                    return

                if "subs_merge" in self.cfg.steps:
                    # Validate manifest presence
                    if not manifest_path.exists():
                        raise FileNotFoundError(
                            f"Missing manifest for subs_merge: {manifest_path}\n"
                            "Hint: run 'subs_list' first, or set [io].manifest to an existing manifest file."
                        )
                    # Auto-named merged output
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

            # ---- FILE FLOWS (mindmap/qa/formatting) -----------------------------
            self._ensure_file_mode()
            text = self.cfg.input_path.read_text(encoding="utf-8")
            ctx = RunContext(text=text)

            # CHUNK
            if "chunk" in self.cfg.steps:
                ctx = self.chunk_stage.run(ctx, app.chunk.max_tokens, self.store, progress,
                                           debug=self.debug, force=self.cfg.force)
            else:
                loaded = self.store.load_debug("chunks.json")
                if loaded is not None:
                    ctx.chunks = loaded

            # REFORMAT
            if "reformat" in self.cfg.steps:
                ctx = self.reformat_text_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
                self.md_exporter.export_bullets(getattr(ctx, "reformat_outputs", []),
                                                self.store.resolve_workspace_path("reformatted.md"))
                self.console.log(f"✅ reformatted markdown saved to: {self.store.resolve_workspace_path('reformatted.md')}")

            # CLEAN FOR MAP
            if "clean_for_map" in self.cfg.steps:
                ctx = self.clean_for_map_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
                self.md_exporter.export_bullets(getattr(ctx, "clean_for_map_outputs", []),
                                                self.store.resolve_workspace_path("clean_for_map.md"))
                self.console.log(f"✅ reformatted markdown saved to: {self.store.resolve_workspace_path('clean_for_map.md')}")

            # BULLETS
            if "bullets" in self.cfg.steps:
                ctx = self.bullets_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
                self.md_exporter.export_bullets(getattr(ctx, "bullets_outputs", []),
                                                self.store.resolve_workspace_path("bullets.md"))
                self.console.log(f"✅ Bulleted markdown saved to: {self.store.resolve_workspace_path('bullets.md')}")

            # QA
            if "qa" in self.cfg.steps:
                ctx = self.qa_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
                self.md_exporter.export_qa(ctx.chunks, self.store.resolve_workspace_path("qa.md"))
            else:
                loaded = self.store.load_debug("chunks_with_qa.json")
                if loaded is not None:
                    ctx.chunks = loaded

            # TREE/CLUSTER/MERGE/REFINE/MAP
            if "tree" in self.cfg.steps:
                ctx = self.tree_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
            if "cluster" in self.cfg.steps:
                ctx = self.cluster_stage.run(ctx, self.store, progress, force=self.cfg.force)
            if "merge" in self.cfg.steps:
                ctx = self.merge_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
            if "refine" in self.cfg.steps:
                ctx = self.refine_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
            if "map" in self.cfg.steps:
                ctx = self.map_stage.run(ctx, self.store, progress, executor=self.executor,
                                         force=self.cfg.force, map_batch_override=self.cfg.map_batch_override)

            if ctx.final_tree:
                out_json = self.store.resolve_workspace_path("mindmap.json")
                self.json_exporter.export_mindmap(ctx.final_tree, out_json)
                self.console.log(f"✅ Mindmap saved to: {out_json}")

                mm_md = self.store.resolve_workspace_path("mindmap.markmap.md")
                self.md_exporter.export_markmap(ctx.final_tree, mm_md)
