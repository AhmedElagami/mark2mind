import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseLanguageModel
from langchain.output_parsers import PydanticOutputParser
from mark2mind.utils.prompt_loader import load_prompt
from mark2mind.utils.tree_helper import normalize_tree


class MergedTreeSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Merged hierarchical mindmap structure")


class TreeMergeChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("merge_tree").strip()

        self.parser = PydanticOutputParser(pydantic_object=MergedTreeSchema)

        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "Tree A (JSON):\n{tree_a}\n\n"
            "Tree B (JSON):\n{tree_b}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        self.chain = (self.prompt | llm | self.parser).with_config(
            run_name="TreeMergeChain",
            callbacks=callbacks,
            tags=["mark2mind","tree","merge"]
        )

    def invoke(self, tree_a: Dict[str, Any], tree_b: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        payload = {
            "tree_a": json.dumps(tree_a, indent=2, ensure_ascii=False),
            "tree_b": json.dumps(tree_b, indent=2, ensure_ascii=False),
        }
        result: MergedTreeSchema = self.chain.invoke(payload, config=config)
        merged = result.model_dump()["tree"]
        return normalize_tree(merged)
