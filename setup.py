from setuptools import setup, find_packages

setup(
    name="mark2mind",
    version="0.1.0",
    description="Semantic mindmap and Q&A generator from Markdown using LLMs",
    author="Ahmed Elagami",
    author_email="ael3agamy15@gmail.com",
    url="https://github.com/your/repo",
    packages=find_packages(),
    include_package_data=True,                 # uses MANIFEST.in for sdist; package_data for wheel
    package_data={"mark2mind": [
        "recipes/*.toml",
        "prompts/*.txt",                       # non-recursive; rely on MANIFEST for subdirs
    ]},
    install_requires=[
        "pydantic",
        "markdown-it-py[linkify]",
        "python-slugify",
        "rich",
        "toml",
        "markdownify",
        "openai",
        "langchain",
        "langchain-core",
        "langchain-community",
        "langchain-deepseek",
        "huggingface_hub",
        "tokenizers",
        "numpy",
        "scipy",
        "scikit-learn",
        "semchunk"
    ],
    extras_require={
        "dev": [
            "pytest",
            "pyinstaller",
        ],
        "lite": [
            "numpy",
        ],
    },
    entry_points={"console_scripts": ["mark2mind=mark2mind.main:main"]},
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Microsoft :: Windows",
    ],
)
