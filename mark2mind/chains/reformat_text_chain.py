from __future__ import annotations

import json
from typing import Dict, Optional, Union

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel, Field

from mark2mind.utils.prompt_loader import load_prompt


class MarkdownResult(BaseModel):
    markdown: str = Field(..., description="Reformatted Markdown (no leading triple backticks, no whole-document fences).")


class ReformatTextChain:
    def __init__(
        self,
        llm: BaseLanguageModel,
        prompt_name: str = "reformat_text",
        prompt_text: Optional[str] = None,
        callbacks=None,
    ):
        base_prompt = (prompt_text or load_prompt(prompt_name)).strip()
        self.parser = PydanticOutputParser(pydantic_object=MarkdownResult)

        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "{input_label}\n{markdown}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
            input_label="INPUT:",
        )

        name_shim = RunnableLambda(lambda x: x).with_config(run_name="RefromatTextChain")
        self.chain = (self.prompt | llm | self.parser | name_shim).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "reformat", "convert", "class:RefromatTextChain"],
        )

    @staticmethod
    def _extract_markdown_payload(chunk: Union[str, Dict]) -> str:
        if isinstance(chunk, str):
            return chunk.strip()
        if not isinstance(chunk, dict) or chunk is None:
            return ""
        for k in ("markdown", "text", "content", "md_text"):
            v = chunk.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        if "blocks" in chunk:
            try:
                return json.dumps(chunk["blocks"], indent=2, ensure_ascii=False)
            except Exception:
                return ""
        return ""

    @staticmethod
    def _sanitize_markdown(md: str) -> str:
        md = (md or "").replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        if md.lstrip().startswith("```"):
            md = "\n" + md
        return md

    def invoke(self, chunk: Union[str, Dict], config: Optional[Dict] = None) -> str:
        payload = self._extract_markdown_payload(chunk)
        if not payload:
            return "InputError: Invalid or malformed input format."
        result: MarkdownResult = self.chain.invoke({"markdown": payload}, config=config)
        return self._sanitize_markdown(result.markdown)
