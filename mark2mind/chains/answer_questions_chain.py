import json
from typing import Dict, Any, List, Literal, Optional
from pydantic import BaseModel, Field, RootModel

from langchain_core.language_models import BaseLanguageModel
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from mark2mind.utils.prompt_loader import load_prompt
from langchain_core.runnables import RunnableLambda



class AnswerSchema(BaseModel):
    question: str
    answer: str
    element_id: str
    type: Literal["paragraph", "code","table","image"]
    element_caption: Optional[str] = None


class AnswerList(RootModel[List[AnswerSchema]]):
    pass


class AnswerQuestionsChain:
    def __init__(self, llm: BaseLanguageModel, callbacks=None):
        base_prompt = load_prompt("qa_answer").strip()
        self.parser = PydanticOutputParser(pydantic_object=AnswerList)
        self.prompt = PromptTemplate.from_template(
            "{base_prompt}\n\n{format_instructions}\n\n"
            "Markdown blocks (JSON):\n{markdown_blocks}\n\n"
            "Questions (JSON array):\n{questions}"
        ).partial(
            base_prompt=base_prompt,
            format_instructions=self.parser.get_format_instructions(),
        )

        name_shim = RunnableLambda(lambda x: x).with_config(run_name="AnswerQuestionsChain")

        self.chain = (
            self.prompt | llm | self.parser | name_shim
        ).with_config(
            callbacks=callbacks,
            tags=["mark2mind", "qa", "answer", "class:AnswerQuestionsChain"],
        )


    def invoke(self, chunk: Dict, questions: List[Dict[str, Any]], config: Optional[Dict] = None) -> List[Dict[str, Any]]:
        input_data = {
            "markdown_blocks": json.dumps(chunk.get("blocks", []), indent=2, ensure_ascii=False),
            "questions": json.dumps(questions, indent=2, ensure_ascii=False),
        }
        result: AnswerList = self.chain.invoke(input_data, config=config)
        return [a.model_dump() for a in result.root]
