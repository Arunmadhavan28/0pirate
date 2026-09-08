from setuptools import setup, find_packages
import os

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="0pirate",
    version="0.1.4",
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
        "spacy>=3.7.0",
        "mcp>=0.1.0",
        "regex>=2023.10.3"
    ],
    entry_points={
        "console_scripts": [
            "0pirate=main:app",
        ],
    },
)
