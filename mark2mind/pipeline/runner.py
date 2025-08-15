from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict, Any
from rich.console import Console

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
    Thin orchestrator around pipeline stages.
    """

    def __init__(
        self,
        config: RunConfig,
        *,
        debug: bool = False,
        callbacks=None,
        llm_factory=None,
        # either pass ready-made chain instances OR rely on llm_factory to create them per-thread
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

        self.store = ArtifactStore(config.debug_dir, config.output_dir, config.file_id)
        self.retryer = Retryer(max_retries=config.max_retries, min_delay_sec=config.min_delay_sec)
        self.llm_pool = LLMFactoryPool(llm_factory)
        self.executor = ExecutorProvider(max_workers=config.executor_max_workers)

        # stage instances
        self.chunk_stage = ChunkStage()
        self.qa_stage = QAStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instances={"qa_q": qa_question_chain, "qa_a": qa_answer_chain})
        self.tree_stage = TreeStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instance=chunk_chain)
        self.cluster_stage = ClusterStage()
        self.merge_stage = MergeStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instance=merge_chain)
        self.refine_stage = RefineStage(self.llm_pool, self.retryer, callbacks=callbacks, merge_chain_instance=merge_chain, refine_chain_instance=refine_chain)
        self.map_stage = MapContentStage(self.llm_pool, self.retryer, callbacks=callbacks, chain_instance=content_chain)
        self.bullets_stage = BulletsStage(self.llm_pool, self.retryer, callbacks=callbacks)


        self.md_exporter = MarkdownExporter()
        self.json_exporter = JSONExporter()

    def run(self):
        # read input
        text = Path(self.cfg.input_file).read_text(encoding="utf-8")
        ctx = RunContext(text=text)

        with RichProgressReporter(self.console) as progress:
            # chunk
            if "chunk" in self.cfg.steps:
                ctx = self.chunk_stage.run(ctx, self.store, progress, debug=self.debug, force=self.cfg.force)
            else:
                loaded = self.store.load_debug("chunks.json")
                if loaded is not None:
                    ctx.chunks = loaded
            # bullets
            if "bullets" in self.cfg.steps: 
                            ctx = self.bullets_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
                            bullets_md = self.cfg.output_dir / f"{self.cfg.file_id}_bullets.md"
                            self.md_exporter.export_bullets(getattr(ctx, "bullets_outputs", []), bullets_md)
                            self.console.log(f"✅ Bulleted markdown saved to: {bullets_md}")
            # qa
            if "qa" in self.cfg.steps:
                ctx = self.qa_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)
                # export QA md
                qa_md = self.cfg.output_dir / f"{self.cfg.file_id}_qa.md"
                self.md_exporter.export_qa(ctx.chunks, qa_md)
            else:
                loaded = self.store.load_debug("chunks_with_qa.json")
                if loaded is not None:
                    ctx.chunks = loaded

            # tree
            if "tree" in self.cfg.steps:
                ctx = self.tree_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)

            # cluster
            if "cluster" in self.cfg.steps:
                ctx = self.cluster_stage.run(ctx, self.store, progress, force=self.cfg.force)

            # merge
            if "merge" in self.cfg.steps:
                ctx = self.merge_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)

            # refine
            if "refine" in self.cfg.steps:
                ctx = self.refine_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force)

            # map
            if "map" in self.cfg.steps:
                ctx = self.map_stage.run(ctx, self.store, progress, executor=self.executor, force=self.cfg.force, map_batch_override=self.cfg.map_batch_override)

        # outputs
        if ctx.final_tree:
            out_json = self.cfg.output_dir / f"{self.cfg.file_id}_mindmap.json"
            self.json_exporter.export_mindmap(ctx.final_tree, out_json)
            self.console.log(f"✅ Mindmap saved to: {out_json}")

            mm_md = self.cfg.output_dir / f"{self.cfg.file_id}_mindmap.markmap.md"
            self.md_exporter.export_markmap(ctx.final_tree, mm_md)
        return ctx
