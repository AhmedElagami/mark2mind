import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.language_models import BaseLanguageModel
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from mark2mind.utils.prompt_loader import load_prompt
from mark2mind.utils.tree_helper import normalize_tree


class TreeOutputSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Hierarchical mindmap structure")
    tags: List[str] = Field(..., description="Flat list of semantic keywords")


class ChunkTreeChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("chunk_tree").strip()

        self.parser = PydanticOutputParser(pydantic_object=TreeOutputSchema)

        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "Markdown blocks (JSON):\n{markdown_blocks}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        self.chain = (self.prompt | llm | self.parser).with_config(
            run_name="ChunkTreeChain",
            callbacks=callbacks,
            tags=["mark2mind","tree","chunk"]
        )

    def invoke(self, chunk: Dict, config: Optional[Dict] = None) -> Dict[str, Any]:
        markdown_json = json.dumps(chunk.get("blocks", []), indent=2, ensure_ascii=False)
        result: TreeOutputSchema = self.chain.invoke({"markdown_blocks": markdown_json}, config=config)
        out = result.model_dump()
        out["tree"] = normalize_tree(out["tree"])
        return out
