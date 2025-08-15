import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from mark2mind.utils.prompt_loader import load_prompt
from mark2mind.utils.tree_helper import normalize_tree
from langchain_core.runnables import RunnableLambda

class RefinedTreeSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Refined final hierarchical mindmap structure")

class TreeRefineChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("refine_tree").strip()
        self.parser = PydanticOutputParser(pydantic_object=RefinedTreeSchema)
        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "Merged tree (JSON):\n{tree}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        name_shim = RunnableLambda(lambda x: x).with_config(run_name="TreeRefineChain")

        self.chain = (
            self.prompt | llm | self.parser | name_shim
        ).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "tree", "refine", "class:TreeRefineChain"],
        )


    def invoke(self, tree: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        payload = {"tree": json.dumps(tree, indent=2, ensure_ascii=False)}
        result: RefinedTreeSchema = self.chain.invoke(payload, config=config)
        refined = result.model_dump()["tree"]
        return normalize_tree(refined)
