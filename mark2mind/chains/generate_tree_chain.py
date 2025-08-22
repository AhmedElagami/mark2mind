import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.language_models import BaseLanguageModel
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from mark2mind.utils.prompt_loader import load_prompt
from mark2mind.utils.tree_helper import normalize_tree, fallback_tags_from_tree

from langchain_core.runnables import RunnableLambda

class TreeOutputSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Hierarchical mindmap structure")
    tags: List[str] = Field(default_factory=list, description="Flat list of semantic keywords")


_empty_tag_chunks = 0


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

        name_shim = RunnableLambda(lambda x: x).with_config(run_name="ChunkTreeChain")

        self.chain = (
            self.prompt | llm | self.parser | name_shim
        ).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "tree", "chunk", "class:ChunkTreeChain"],
        )


    def invoke(self, chunk: Dict, config: Optional[Dict] = None) -> Dict[str, Any]:
        markdown_json = json.dumps(chunk.get("blocks", []), indent=2, ensure_ascii=False)
        result: TreeOutputSchema = self.chain.invoke({"markdown_blocks": markdown_json}, config=config)
        out = result.model_dump()
        out["tree"] = normalize_tree(out["tree"])
        if not out["tags"]:
            global _empty_tag_chunks
            _empty_tag_chunks += 1
            print("[warn] tags empty for chunk; falling back to []")
            out["tags"] = fallback_tags_from_tree(out["tree"])
        return out
