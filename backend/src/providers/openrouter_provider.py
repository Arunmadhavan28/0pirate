from __future__ import annotations
import os, requests, json
from .base import LLMProvider
from ..config import settings

class OpenRouterProvider(LLMProvider):
    name = "openrouter"

    def complete(self, prompt: str, model: str | None = None, **kwargs) -> str:
        api_key = self.api_key or os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set and no key passed dynamically.")
        
        # Default to a highly capable, cheap model if none is specified
        model = model or "anthropic/claude-3.5-sonnet"
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://0pirate.com", # Required by OpenRouter
            "X-Title": "0Pirate Zero-Knowledge Proxy", # Required by OpenRouter
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get('temperature', 0.2),
            "max_tokens": kwargs.get('max_tokens', 4096)
        }

        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=300)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
