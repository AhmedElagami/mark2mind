import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, RootModel

from langchain_core.language_models import BaseLanguageModel
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from mark2mind.utils.prompt_loader import load_prompt


class QuestionSchema(BaseModel):
    question: str = Field(..., description="Generated question")
    element_id: str
    type: str
    element_caption: str


class QuestionList(RootModel[List[QuestionSchema]]):
    pass


class GenerateQuestionsChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("qa_generate").strip()

        self.parser = PydanticOutputParser(pydantic_object=QuestionList)

        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\nMarkdown blocks (JSON):\n{markdown_blocks}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        # Bind callbacks + run_name once
        self.chain = (self.prompt | llm | self.parser).with_config(
            run_name="GenerateQuestionsChain",
            callbacks=callbacks,
            tags=["mark2mind", "qa"]
        )

    def invoke(self, chunk: Dict, config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        blocks_json = json.dumps(chunk.get("blocks", []), indent=2, ensure_ascii=False)
        result: QuestionList = self.chain.invoke({"markdown_blocks": blocks_json}, config=config)
        return [q.model_dump() for q in result.root]
