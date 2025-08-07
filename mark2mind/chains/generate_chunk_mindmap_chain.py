
# from langchain.chat_models import ChatOpenAI
# from mindmap_langchain.chains.generate_chunk_chain import ChunkTreeChain

# llm = ChatOpenAI(model="gpt-4", temperature=0.5)
# chain = ChunkTreeChain(llm=llm, prompt_path="prompts/prompt1.txt")

# result = chain.invoke(chunk)
# print(result["tree"])
# print(result["tags"])


import json
from typing import List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.output_parsers import StructuredOutputParser
from langchain.chains import LLMChain
from mindmap_langchain.utils.tracing import LocalTracingHandler
from utils.prompt_loader import load_prompt


class TreeOutputSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Hierarchical mindmap structure")
    tags: List[str] = Field(..., description="Flat list of semantic keywords")


class ChunkTreeChain:
    """
    LangChain-compatible class to generate a semantic tree and tag list
    from a Markdown chunk using structured output parsing.
    """

    def __init__(self, llm: BaseLanguageModel):
        # Load your long instructional prompt from file
        base_prompt = load_prompt("chunk_tree")


        # Build output parser
        self.parser = StructuredOutputParser.from_pydantic(TreeOutputSchema)
        format_instructions = self.parser.get_format_instructions()

        # Add parsing instructions to the end of the prompt
        full_prompt = base_prompt.strip() + "\n\n" + format_instructions

        self.prompt = PromptTemplate(
            template=full_prompt,
            input_variables=["markdown_blocks"]
        )

        self.chain = LLMChain(
            llm=llm,
            prompt=self.prompt
        )

    def invoke(self, chunk: Dict) -> Dict[str, Any]:
        """
        Run the LLM chain on a single Markdown chunk.

        Returns:
            {
                "tree": Dict,
                "tags": List[str]
            }
        """
        markdown_json = json.dumps(chunk.get("blocks", []), indent=2, ensure_ascii=False)
        response = self.chain.invoke({"markdown_blocks": markdown_json})

        # Extract and parse the structured result
        output = self.parser.invoke(response["text"])
        return output.dict()
