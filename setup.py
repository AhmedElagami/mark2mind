from setuptools import setup, find_packages

setup(
    name="mark2mind",
    version="0.1.0",
    description="Semantic mindmap and Q&A generator from Markdown using LLMs",
    author="Ahmed Elagami",
    author_email="ael3agamy15@gmail.com",
    url="https://github.com/AhmedElagami/mark2mind",
    packages=find_packages(),
    python_requires=">=3.11,<3.12",  # use 3.11 for PyInstaller+SciPy stability
    include_package_data=True,
    package_data={
        "mark2mind": [
            "recipes/*.toml",
            "prompts/*.txt",
            "vendor_models/**/*",
        ]
    },
    install_requires=[
        "pydantic>=2,<3",
        "markdown-it-py[linkify]>=3,<4",
        "python-slugify>=8,<9",
        "rich>=13,<14",
        "toml>=0.10,<1",
        "markdownify>=0.13,<1",
        "openai>=1.30,<2",
        "langchain",
        "langchain-core",
        "langchain-community",
        "langchain-deepseek",
        "huggingface_hub>=0.23,<1",
        "tokenizers>=0.15,<0.16",
        "numpy==1.26.4",
        "scipy==1.11.4",
        "scikit-learn==1.4.2",
        "semchunk>=0.2,<0.3",
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
