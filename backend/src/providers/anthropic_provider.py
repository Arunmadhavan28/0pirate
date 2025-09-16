from __future__ import annotations
import os, requests, json
from .base import LLMProvider
from ..config import settings

class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None):
        """Initialize the provider with a specific API key or fall back to settings."""
        self.api_key = api_key or settings.anthropic_key

    def complete(self, prompt: str, model: str | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set.")
        
        model = model or "claude-3-haiku-20240307"
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        data = r.json()
        return "".join(part.get("text", "") for part in data.get("content", []))