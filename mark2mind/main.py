import argparse
import json
import os
from pathlib import Path
from typing import List, Dict
from langchain.chat_models import ChatOpenAI

from mindmap_langchain.runner.step_runner import StepRunner  # <- New class you'll create
from mindmap_langchain.chains.generate_chunk_chain import ChunkTreeChain
from mindmap_langchain.chains.merge_tree_chain import TreeMergeChain
from mindmap_langchain.chains.refine_tree_chain import TreeRefineChain
from mindmap_langchain.chains.attach_content_chain import ContentMappingChain
from mindmap_langchain.chains.generate_questions_chain import GenerateQuestionsChain
from mindmap_langchain.chains.answer_questions_chain import AnswerQuestionsChain
from mindmap_langchain.utils.tracing import LocalTracingHandler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run semantic mindmap generation with Q&A from Markdown")
    parser.add_argument("input_file", type=str, help="Path to raw Markdown file")
    parser.add_argument("file_id", type=str, help="Unique debug/output identifier")
    parser.add_argument("--steps", type=str, help="Comma-separated steps to run (e.g. chunk,qa,tree,map)", required=True)
    parser.add_argument("--debug", action="store_true", help="Enable debug output and tracing")
    parser.add_argument("--force", action="store_true", help="Force re-run of all steps, ignore debug cache")
    parser.add_argument("--enable-tracing", action="store_true", help="Enable local tracing to debug/traces")

    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    tracer = LocalTracingHandler() if args.enable_tracing else None
    callbacks = [tracer] if tracer else None

    def load_llm() -> ChatOpenAI:
        return ChatOpenAI(model="gpt-4", temperature=0, callbacks=callbacks)

    llm = load_llm()

    # Initialize LangChain components
    runner = StepRunner(
        input_file=args.input_file,
        file_id=args.file_id,
        steps=steps,
        debug=args.debug,
        chunk_chain=ChunkTreeChain(llm, prompt_path="prompts/prompt1.txt"),
        merge_chain=TreeMergeChain(llm, prompt_path="prompts/merge.txt"),
        refine_chain=TreeRefineChain(llm, prompt_path="prompts/refine.txt"),
        content_chain=ContentMappingChain(llm, prompt_path="prompts/map.txt"),
        qa_question_chain=GenerateQuestionsChain(llm, prompt_path="prompts/qa_generate.txt"),
        qa_answer_chain=AnswerQuestionsChain(llm, prompt_path="prompts/qa_answer.txt"),
        force=args.force
    )

    runner.run()
