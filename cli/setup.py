from setuptools import setup, find_packages
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="0pirate",
    version="0.2.1",
    description="Zero-Knowledge AI Security Middleware for Agents and IDEs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="0Pirate Team",
    packages=find_packages(),
    install_requires=[
        "typer>=0.9.0",
        "requests>=2.31.0",
        "rich>=13.0.0",
        "pyyaml>=6.0.0",
        "regex>=2023.10.3",
        "mcp>=2.2.0",
        "starlette>=0.37.0",
        "uvicorn>=0.30.0",
    ],
    extras_require={
        "nlp": ["spacy>=3.7.0"],
        "all": ["spacy>=3.7.0", "prometheus-client"],
    },
    entry_points={
        "console_scripts": [
            "0pirate=main:app",
            "0pirate-mcp=mcp_server:main",
        ],
    },
)
