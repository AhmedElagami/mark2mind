from setuptools import setup, find_packages

setup(
    name="mark2mind",
    version="0.1.0",
    description="Semantic mindmap and Q&A generator from Markdown using LLMs",
    author="Ahmed Elagami",
    author_email="ael3agamy15@gmail.com",
    url="https://github.com/AhmedElagami/mark2mind",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "mark2mind": [
            "recipes/*.toml",
            "prompts/*.txt",
            "vendor_models/**/*",
        ]
    },
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
        "semchunk",
    ],
    extras_require={
        "dev": ["pytest", "pyinstaller==6.6"],
        "lite": ["numpy==1.26.4"],
    },
    entry_points={"console_scripts": ["mark2mind=mark2mind.main:main"]},
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
)
