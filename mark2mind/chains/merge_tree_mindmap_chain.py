import json
from typing import Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_core.language_models import BaseLanguageModel
from langchain.output_parsers import JsonOutputParser
from utils.prompt_loader import load_prompt


class MergedTreeSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Merged hierarchical mindmap structure")


class TreeMergeChain:
    """
    LangChain-compatible class to merge two mindmap trees into one
    using a prompt template and structured JSON output parsing.
    """

    def __init__(self, llm: BaseLanguageModel):
        # Load tree merge prompt template from file
        base_prompt = load_prompt("merge_tree")

        # Define output parser
        self.parser = JsonOutputParser(pydantic_object=MergedTreeSchema)
        format_instructions = self.parser.get_format_instructions()

        # Final prompt with parsing instructions
        full_prompt = base_prompt.strip() + "\n\n" + format_instructions

        self.prompt = PromptTemplate(
            template=full_prompt,
            input_variables=["tree_a", "tree_b"]
        )

        self.chain = LLMChain(
            llm=llm,
            prompt=self.prompt
        )

    def invoke(self, tree_a: Dict[str, Any], tree_b: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two trees using the LLM and return a structured JSON tree.

        Args:
            tree_a (Dict): First tree
            tree_b (Dict): Second tree

        Returns:
            Dict[str, Any]: Merged tree
        """
        input_data = {
            "tree_a": json.dumps(tree_a, indent=2, ensure_ascii=False),
            "tree_b": json.dumps(tree_b, indent=2, ensure_ascii=False)
        }
        response = self.chain.invoke(input_data)
        output = self.parser.invoke(response["text"])
        return output.tree
