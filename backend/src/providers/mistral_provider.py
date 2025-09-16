from __future__ import annotations
import os, requests, json
from .base import LLMProvider
from ..config import settings

class MistralProvider(LLMProvider):
    name = "mistral"

    def __init__(self, api_key: str | None = None):
        """Initialize the provider with a specific API key or fall back to settings."""
        self.api_key = api_key or settings.mistral_key

    def complete(self, prompt: str, model: str | None = None) -> str:
        if not self.api_key:
            raise RuntimeError("MISTRAL_API_KEY not set.")
        
        model = model or "mistral-small-latest"
        url = "https://api.mistral.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]