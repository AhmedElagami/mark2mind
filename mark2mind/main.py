from datetime import datetime
import os
import uuid
os.environ["TRANSFORMERS_NO_AVAILABLE_BACKENDS"] = "1"

import argparse
import json
from pathlib import Path
from typing import List, Dict
from langchain_deepseek import ChatDeepSeek
from mark2mind.runner.step_runner import StepRunner
from mark2mind.chains.generate_tree_chain import ChunkTreeChain
from mark2mind.chains.merge_tree_chain import TreeMergeChain
from mark2mind.chains.refine_tree_chain import TreeRefineChain
from mark2mind.chains.map_content_mindmap_chain import ContentMappingChain
from mark2mind.chains.generate_questions_chain import GenerateQuestionsChain
from mark2mind.chains.answer_questions_chain import AnswerQuestionsChain
from mark2mind.utils.tracing import LocalTracingHandler

def main():
    parser = argparse.ArgumentParser(description="Run semantic mindmap generation with Q&A from Markdown")
    parser.add_argument("input_file", type=str, help="Path to raw Markdown file")
    parser.add_argument("file_id", type=str, help="Unique debug/output identifier")
    parser.add_argument("--steps", type=str, help="Comma-separated steps to run (e.g. chunk,qa,tree,map)", required=True)
    parser.add_argument("--debug", action="store_true", help="Enable debug output and tracing")
    parser.add_argument("--force", action="store_true", help="Force re-run of all steps, ignore debug cache")
    parser.add_argument("--enable-tracing", action="store_true", help="Enable local tracing to debug/traces")

    args = parser.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    tracer = LocalTracingHandler(base_dir="debug", file_id=args.file_id, run_id=run_id) if args.enable_tracing else None
    callbacks = [tracer] if tracer else None

    def load_llm() -> ChatDeepSeek:
        os.environ["DEEPSEEK_API_KEY"] = "sk-06a8bbe5dd014a6aac5b4c182c06640e"
        llm = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.3,
            max_tokens=8000,
            timeout=None,
            max_retries=2,
        )
        return llm

    llm = load_llm()

    runner = StepRunner(
        input_file=args.input_file,
        file_id=args.file_id,
        steps=steps,
        debug=args.debug,
        chunk_chain=ChunkTreeChain(llm, callbacks=callbacks),
        merge_chain=TreeMergeChain(llm, callbacks=callbacks),
        refine_chain=TreeRefineChain(llm, callbacks=callbacks),
        content_chain=ContentMappingChain(llm, callbacks=callbacks),
        qa_question_chain=GenerateQuestionsChain(llm, callbacks=callbacks),
        qa_answer_chain=AnswerQuestionsChain(llm, callbacks=callbacks),
        force=args.force,
        run_id=run_id,
        llm_factory=load_llm,
        callbacks=callbacks
    )


    runner.run()

if __name__ == "__main__":
    main()