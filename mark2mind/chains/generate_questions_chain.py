import json
from typing import Dict, Any, List
from pathlib import Path
from pydantic import BaseModel, Field
from langchain.prompts import PromptTemplate
from langchain.output_parsers import JsonOutputParser
from langchain.chains import LLMChain
from langchain_core.language_models import BaseLanguageModel
from utils.prompt_loader import load_prompt


class QuestionSchema(BaseModel):
    question: str = Field(..., description="Generated question")
    element_id: str
    element_type: str


class GenerateQuestionsChain:
    def __init__(self, llm: BaseLanguageModel):
        base_prompt = load_prompt("qa_generate")

        self.parser = JsonOutputParser(pydantic_object=List[QuestionSchema])
        format_instructions = self.parser.get_format_instructions()

        self.prompt = PromptTemplate(
            template=base_prompt.strip() + "\n\n" + format_instructions,
            input_variables=["markdown_blocks"]
        )

        self.chain = LLMChain(llm=llm, prompt=self.prompt)

    def invoke(self, chunk: Dict) -> List[Dict[str, Any]]:
        blocks_json = json.dumps(chunk.get("blocks", []), indent=2, ensure_ascii=False)
        response = self.chain.invoke({"markdown_blocks": blocks_json})
        return self.parser.invoke(response["text"])
