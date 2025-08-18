import json
from typing import Dict, Optional, Union
from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseLanguageModel
from mark2mind.utils.exporters import unwrap_if_single_fence_md
from mark2mind.utils.prompt_loader import load_prompt
from langchain_core.runnables import RunnableLambda
from markdown_it import MarkdownIt
class FormatBulletsChain:
    def __init__(
        self,
        llm: BaseLanguageModel,
        prompt_name: str = "format_bullets",
        prompt_text: Optional[str] = None,
        callbacks=None,
    ):
        base_prompt = (prompt_text or load_prompt(prompt_name)).strip()
        self.prompt = PromptTemplate(
            template=base_prompt,
            input_variables=["markdown"],
        )
        name_shim = RunnableLambda(lambda x: x).with_config(run_name="FormatBulletsChain")
        self.chain = (
            self.prompt | llm | name_shim
        ).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "outline", "convert", "class:FormatBulletsChain"],
        )

    def _postprocess(self, obj) -> str:
        raw = self._to_text(obj)
        raw = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        return unwrap_if_single_fence_md(raw)

    @staticmethod
    def _extract_markdown_payload(chunk: Union[str, Dict]) -> str:
        if isinstance(chunk, str):
            return chunk.strip()
        if not isinstance(chunk, dict) or chunk is None:
            return ""
        for k in ("markdown", "text", "content", "md_text"):
            if isinstance(chunk.get(k), str) and chunk[k].strip():
                return chunk[k].strip()
        if "blocks" in chunk:
            try:
                return json.dumps(chunk["blocks"], indent=2, ensure_ascii=False)
            except Exception:
                return ""
        return ""

    def _to_text(self, obj) -> str:
        # Normalize any LLM return into a plain string
        try:
            # LangChain messages
            content = getattr(obj, "content", None)
            if isinstance(content, str):
                return content
            # Some models return a list of messages or generations
            if isinstance(obj, list) and obj and hasattr(obj[0], "content"):
                return obj[0].content
            if isinstance(obj, dict) and isinstance(obj.get("content"), str):
                return obj["content"]
            if isinstance(obj, str):
                return obj
            # Last resort
            return str(obj)
        except Exception:
            return ""

    def invoke(self, chunk: Union[str, Dict], config: Optional[Dict] = None) -> str:
        payload = self._extract_markdown_payload(chunk)
        if not payload:
            return "InputError: Invalid or malformed input format."
        result_obj = self.chain.invoke({"markdown": payload}, config=config)
        return self._postprocess(result_obj)
