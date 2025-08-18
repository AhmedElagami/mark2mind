from setuptools import setup, find_packages

setup(
    name="mark2mind",
    version="0.1.0",
    description="Semantic mindmap and Q&A generator from Markdown using LangChain and LLMs",
    author="Ahmed Elagami",
    author_email="ael3agamy15@gmail.com",
    packages=find_packages(),
    include_package_data=True,
    package_data={"mark2mind": ["recipes/*.toml", "prompts/**/*.txt"]},
    install_requires=[
        "langchain",
        "langchain-core",
        "langchain-community",
        "langchain-deepseek",
        "openai",
        "pydantic",
        "transformers",
        "markdown-it-py[linkify]",
        "python-slugify",
        "scikit-learn",
        "rich",
        "semchunk",
        "toml",
        "markdownify",
    ],
    entry_points={
        "console_scripts": [
            "mark2mind=mark2mind.main:main",
        ]
    },
    python_requires=">=3.8",
)
