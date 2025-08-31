# FILE: mark2mind/chains/note_generation_chains.py
from __future__ import annotations
import json
from typing import Dict, List, Any, Optional
from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from mark2mind.utils.prompt_loader import load_prompt

class NoteLeafChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        tpl = load_prompt("note_leaf")
        self.prompt = PromptTemplate.from_template(tpl)
        name = RunnableLambda(lambda x: x).with_config(run_name="NoteLeafChain")
        self.chain = (self.prompt | llm | name).with_config(callbacks=callbacks, tags=["mark2mind","notes","class:NoteLeafChain"])

    def invoke(self, **vars) -> str:
        return self.chain.invoke(vars)

class NoteBranchChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        tpl = load_prompt("note_branch")
        self.prompt = PromptTemplate.from_template(tpl)
        name = RunnableLambda(lambda x: x).with_config(run_name="NoteBranchChain")
        self.chain = (self.prompt | llm | name).with_config(callbacks=callbacks, tags=["mark2mind","notes","class:NoteBranchChain"])

    def invoke(self, **vars) -> str:
        return self.chain.invoke(vars)

class PrereqPickChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        tpl = load_prompt("prereq_pick")
        self.prompt = PromptTemplate.from_template(tpl)
        name = RunnableLambda(lambda x: x).with_config(run_name="PrereqPickChain")
        self.chain = (self.prompt | llm | name).with_config(callbacks=callbacks, tags=["mark2mind","notes","class:PrereqPickChain"])

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
