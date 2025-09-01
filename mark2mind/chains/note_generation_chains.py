from __future__ import annotations
import json
from typing import Dict, List, Any
from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableSequence
from mark2mind.utils.prompt_loader import load_prompt

def _to_text(msg):
    # Works for AIMessage, ChatGeneration, str
    if isinstance(msg, str):
        return msg
    content = getattr(msg, "content", None)
    if content is not None:
        return content
    # some LLMs return {generations:[{text:...}]}
    text = getattr(msg, "text", None)
    return text if isinstance(text, str) else str(msg)

class NoteLeafChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        tpl = load_prompt("note_leaf")
        prompt = PromptTemplate.from_template(tpl)
        self.chain: RunnableSequence = (prompt | llm | RunnableLambda(_to_text)).with_config(
            callbacks=callbacks, tags=["mark2mind","notes","class:NoteLeafChain"]
        )
    def invoke(self, **vars) -> str:
        return self.chain.invoke(vars)

class NoteBranchChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        tpl = load_prompt("note_branch")
        prompt = PromptTemplate.from_template(tpl)
        self.chain: RunnableSequence = (prompt | llm | RunnableLambda(_to_text)).with_config(
            callbacks=callbacks, tags=["mark2mind","notes","class:NoteBranchChain"]
        )
    def invoke(self, **vars) -> str:
        return self.chain.invoke(vars)

class PrereqPickChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        tpl = load_prompt("prereq_pick")
        prompt = PromptTemplate.from_template(tpl)
        self.chain: RunnableSequence = (prompt | llm | RunnableLambda(_to_text)).with_config(
            callbacks=callbacks, tags=["mark2mind","notes","class:PrereqPickChain"]
        )
    def invoke(self, target: Dict[str,Any], candidates_json: str, graph_children_json: str) -> List[str]:
        out = self.chain.invoke({
            "id": target["id"], "title": target["title"], "path": target["path"], "summary": target["summary"],
            "candidates_json": candidates_json, "graph_children_json": graph_children_json
        })
        try:
            data = json.loads(out)
            return [str(x) for x in data][:5]
        except Exception:
            return []
