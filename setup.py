from setuptools import setup, find_packages

setup(
    name="mark2mind",
    version="0.1.0",
    description="Semantic mindmap and Q&A generator from Markdown using LangChain and LLMs",
    author="Ahmed Elagami",
    author_email="ael3agamy15@gmail.com ",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "langchain>=0.1.0",
        "openai>=1.0.0",
        "pydantic>=2.0.0",
        "transformers>=4.0.0",
        "markdown-it-py>=2.0.0",
        "python-slugify>=8.0.0",
        "scikit-learn>=1.0.0",
        "spacy>=3.0.0",
        "rich>=13.0.0",
        "tiktoken",
    ],
    entry_points={
        "console_scripts": [
            "mark2mind=mark2mind.main:main"
        ]
    },
    python_requires=">=3.8",
)
