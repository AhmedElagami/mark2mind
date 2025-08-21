import json
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, RootModel
from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from mark2mind.utils.prompt_loader import load_prompt
from langchain_core.runnables import RunnableLambda
from typing import Literal

class QARefSchema(BaseModel):
    element_id: str
    type: Literal["qa"]
    target_node_id: str

class QARefList(RootModel[List[QARefSchema]]):
    pass

class QAContentMappingChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("map_content_qa").strip()

        self.parser = PydanticOutputParser(pydantic_object=QARefList)
        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "Tree (JSON):\n{tree}\n\n"
            "Questions (JSON array):\n{content_blocks}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        name_shim = RunnableLambda(lambda x: x).with_config(run_name="QAContentMappingChain")
        self.chain = (
            self.prompt | llm | self.parser | name_shim
        ).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "map", "class:QAContentMappingChain"],
        )

    def invoke(
        self, tree: Dict[str, Any], qa_blocks: List[Dict[str, Any]], config: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        to_send = []
        for b in qa_blocks:
            to_send.append({
                "element_id": b.get("element_id"),
                "type": "qa",
                # only the question text is sent to the model
                "q": b.get("q") or "",
                # keep heading context (it helps routing)
                "heading_path": b.get("heading_path") or [],
            })

        input_data = {
            "tree": json.dumps(tree, indent=2, ensure_ascii=False),
            "content_blocks": json.dumps(to_send, indent=2, ensure_ascii=False),
        }
        result: QARefList = self.chain.invoke(input_data, config=config)
        return [item.model_dump() for item in result.root]
