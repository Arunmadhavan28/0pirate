from setuptools import setup, find_packages

setup(
    name="0pirate",
    version="0.1.0",
    description="Zero-Knowledge AI Security Middleware for Agents and IDEs",
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
