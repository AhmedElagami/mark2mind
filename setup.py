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
        "langchain",  # or latest stable tested with your setup
        "langchain-core",
        "langchain-community",
        "langchain-deepseek",
        "openai",
        "pydantic",
        "transformers",
        "markdown-it-py[linkify]",
        "python-slugify",
        "scikit-learn",
        "spacy",
        "rich",
    ],
    entry_points={
        "console_scripts": [
            "mark2mind=mark2mind.main:main",
            "download_spacy_model=mark2mind.install_hooks.download_spacy_model:download"
        ]
    },
    python_requires=">=3.8",
)
