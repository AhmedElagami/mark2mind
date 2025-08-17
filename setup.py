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
        "spacy",
        "rich",
        "semchunk",
        "toml",
        "markdownify",
    ],
    entry_points={
        "console_scripts": [
            # original
            "mark2mind=mark2mind.main:main",
            "download_spacy_model=mark2mind.install_hooks.download_spacy_model:download",

            # new generic recipes runner
            "m2m=mark2mind.recipes_cli:main",

            # friendly one-shot wrappers
            "m2m-list-subs=mark2mind.recipes_cli:list_subs_main",
            "m2m-merge-subs=mark2mind.recipes_cli:merge_subs_main",
            "m2m-reformat=mark2mind.recipes_cli:reformat_main",
            "m2m-clarify=mark2mind.recipes_cli:clarify_main",
            "m2m-mindmap=mark2mind.recipes_cli:mindmap_main",
            "m2m-mindmap-detailed=mark2mind.recipes_cli:mindmapd_main",
            "m2m-qa=mark2mind.recipes_cli:qa_main",
        ]
    },
    python_requires=">=3.8",
)
