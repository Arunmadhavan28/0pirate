from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# This automatically finds and loads variables from your .env file
load_dotenv()

def _parse_cors_origins() -> list[str]:
    """
    Parses the CORS_ORIGINS environment variable from your .env file,
    which can be a comma-separated list of URLs.
    """
    origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in origins.split(',') if origin.strip()]

@dataclass
class Settings:
    # LLM Provider API Keys
    openai_key: str | None = os.getenv("OPENAI_API_KEY")
    anthropic_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    google_key: str | None = os.getenv("GOOGLE_API_KEY")  # Gemini
    deepseek_key: str | None = os.getenv("DEEPSEEK_API_KEY")
    mistral_key: str | None = os.getenv("MISTRAL_API_KEY")
    groq_key: str | None = os.getenv("GROQ_API_KEY")
    
    # Local LLM Host
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    qwen_host: str = os.getenv("QWEN_HOST", "http://127.0.0.1:11434")
    
    # Supabase Credentials
    supabase_url: str | None = os.getenv("SUPABASE_URL")
    supabase_key: str | None = os.getenv("SUPABASE_KEY")
    supabase_service_key: str | None = os.getenv("SUPABASE_SERVICE_KEY")

    # Razorpay Credentials
    razorpay_key_id: str | None = os.getenv("RAZORPAY_KEY_ID")
    razorpay_key_secret: str | None = os.getenv("RAZORPAY_KEY_SECRET")
    razorpay_webhook_secret: str | None = os.getenv("RAZORPAY_WEBHOOK_SECRET") 

    # CORRECTED: CORS Origins are now correctly read from the .env file
    cors_origins: list[str] = field(default_factory=_parse_cors_origins)

# A single, global instance of your settings that the rest of the app can import
settings = Settings()