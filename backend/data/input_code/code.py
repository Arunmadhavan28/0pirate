# Your Original, Buggy Code
from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv(

@dataclass
class Settings
    openai_key: str | None = os.getenv("OPENAI_API_KEY"
    anthropic_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    google_key: str | None = os.getenv("GOOGLE_API_KEY"  # Gemini
    deepseek_key: str | None = os.getenv("DEEPSEEK_API_KEY"
    mistral_key: str | None = os.getenv("MISTRAL_API_KEY"
    groq_key: str | None = os.getenv("GROQ_API_KEY"
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434
    qwen_host str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"

settings = Settings()

