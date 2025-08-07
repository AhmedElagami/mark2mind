import json
from typing import Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.language_models import BaseLanguageModel
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.output_parsers import JsonOutputParser
from utils.prompt_loader import load_prompt


class RefinedTreeSchema(BaseModel):
    tree: Dict[str, Any] = Field(..., description="Refined final hierarchical mindmap structure")


class TreeRefineChain:
    """
    LangChain-compatible class to refine a merged mindmap tree
    into a cleaner final structure using an LLM and a prompt template.
    """

    def __init__(self, llm: BaseLanguageModel):
        # Load the refinement prompt template from file
        base_prompt = load_prompt("refine_tree")

        # Define structured output parser
        self.parser = JsonOutputParser(pydantic_object=RefinedTreeSchema)
        format_instructions = self.parser.get_format_instructions()

        # Append format instructions to the end of the prompt
        full_prompt = base_prompt.strip() + "\n\n" + format_instructions

        self.prompt = PromptTemplate(
            template=full_prompt,
            input_variables=["tree"]
        )

        self.chain = LLMChain(
            llm=llm,
            prompt=self.prompt
        )

    def invoke(self, tree: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refine the input tree using the LLM and return the structured output.

        Args:
            tree (Dict): Merged but unrefined tree structure

        Returns:
            Dict[str, Any]: Refined tree
        """
        input_data = {
            "tree": json.dumps(tree, indent=2, ensure_ascii=False)
        }
        response = self.chain.invoke(input_data)
        output = self.parser.invoke(response["text"])
        return output.tree
