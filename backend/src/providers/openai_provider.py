from __future__ import annotations
import os, requests, json
from .base import LLMProvider
from ..config import settings

class OpenAIProvider(LLMProvider):
    name = "openai"

    def complete(self, prompt: str, model: str | None = None, **kwargs) -> str:
        api_key = settings.openai_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set.")
        model = model or "gpt-4o"
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # --- FIX APPLIED HERE ---
        # The payload now dynamically includes parameters from kwargs.
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get('temperature', 0.2), # Use passed value or default
            "max_tokens": kwargs.get('max_tokens', 2048)
        }
        # --- END FIX ---

        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=300)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
