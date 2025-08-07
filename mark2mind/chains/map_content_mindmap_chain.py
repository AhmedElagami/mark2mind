import json
from typing import List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import JsonOutputParser
from utils.prompt_loader import load_prompt


class ContentRefSchema(BaseModel):
    element_id: str = Field(..., description="Unique identifier of the content block")
    element_type: str = Field(..., description="Type of content block (e.g. code, table, text)")
    element_caption: str = Field(..., description="Human-readable summary or title")
    target_node_id: str = Field(..., description="Node ID in the tree where this content should be attached")


class ContentMappingChain:
    """
    LangChain-compatible class to map content blocks to specific nodes in a tree structure.
    """

    def __init__(self, llm: BaseLanguageModel):
        # Load prompt template from file
        base_prompt = load_prompt("map_content")

        # Define output parser
        self.parser = JsonOutputParser(pydantic_object=List[ContentRefSchema])
        format_instructions = self.parser.get_format_instructions()

        # Final prompt template
        full_prompt = base_prompt.strip() + "\n\n" + format_instructions

        self.prompt = PromptTemplate(
            template=full_prompt,
            input_variables=["tree", "content_blocks"]
        )

        self.chain = LLMChain(
            llm=llm,
            prompt=self.prompt
        )

    def invoke(self, tree: Dict[str, Any], blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Maps Markdown blocks to tree nodes using an LLM.

        Args:
            tree (Dict): The mindmap tree
            blocks (List[Dict]): Markdown content blocks

        Returns:
            List[Dict]: Each item contains element_id, element_type, element_caption, target_node_id
        """
        input_data = {
            "tree": json.dumps(tree, indent=2, ensure_ascii=False),
            "content_blocks": json.dumps(blocks, indent=2, ensure_ascii=False)
        }
        response = self.chain.invoke(input_data)
        return self.parser.invoke(response["text"])

