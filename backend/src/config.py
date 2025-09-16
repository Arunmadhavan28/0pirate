from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    openai_key: str | None = os.getenv("OPENAI_API_KEY")
    anthropic_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    google_key: str | None = os.getenv("GOOGLE_API_KEY")  # Gemini
    deepseek_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    mistral_key: str | None = os.getenv("MISTRAL_API_KEY")
    groq_key: str | None = os.getenv("GROQ_API_KEY")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    qwen_host: str = os.getenv("QWEN_HOST", "http://127.0.0.1:11434")

    # Supabase
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_key: str | None = os.getenv("SUPABASE_KEY")
    supabase_service_key: str | None = os.getenv("SUPABASE_SERVICE_KEY")

    # Razorpay
    razorpay_key_id: str | None = os.getenv("RAZORPAY_KEY_ID")
    razorpay_key_secret: str | None = os.getenv("RAZORPAY_KEY_SECRET")
    razorpay_webhook_secret: str | None = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    # CORS
    cors_origins: list[str] = field(default_factory=list)


settings = Settings()
