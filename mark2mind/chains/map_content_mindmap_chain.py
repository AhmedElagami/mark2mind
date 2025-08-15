import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, RootModel

from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from mark2mind.utils.prompt_loader import load_prompt
from mark2mind.utils.tree_helper import normalize_tree
from langchain_core.runnables import RunnableLambda
from typing import Literal

class ContentRefSchema(BaseModel):
    element_id: str
    type: Literal["paragraph","code","table","image"]  # optional but safer
    element_caption: str
    target_node_id: str

class ContentRefList(RootModel[List[ContentRefSchema]]):
    pass

class ContentMappingChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("map_content").strip()
        self.parser = PydanticOutputParser(pydantic_object=ContentRefList)
        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "Tree (JSON):\n{tree}\n\n"
            "Content blocks (JSON array):\n{content_blocks}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        name_shim = RunnableLambda(lambda x: x).with_config(run_name="ContentMappingChain")

        self.chain = (
            self.prompt | llm | self.parser | name_shim
        ).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "map", "class:ContentMappingChain"],
        )


    def invoke(self, tree: Dict[str, Any], blocks: List[Dict[str, Any]], config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        input_data = {
            "tree": json.dumps(tree, indent=2, ensure_ascii=False),
            "content_blocks": json.dumps(blocks, indent=2, ensure_ascii=False),
        }
        result: ContentRefList = self.chain.invoke(input_data, config=config)
        return [item.model_dump() for item in result.root]
