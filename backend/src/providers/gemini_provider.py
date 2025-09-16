from __future__ import annotations
import os, requests, json
from .base import LLMProvider
from ..config import settings

class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str | None = None):
        """Initialize the provider with a specific API key or fall back to settings."""
        self.api_key = api_key or settings.google_key

    def complete(self, prompt: str, model: str | None = None, **kwargs) -> str:
        # Use the stored API key from __init__
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY (Gemini) not set.")
        
        model = model or "gemini-1.5-flash"
        # Use self.api_key in the URL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}

        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        generation_config = {}
        
        if 'temperature' in kwargs:
            generation_config['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            generation_config['maxOutputTokens'] = kwargs['max_tokens']

        if generation_config:
            payload['generationConfig'] = generation_config

        r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        data = r.json()
        
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return f"Error: Could not parse Gemini response. Full response: {json.dumps(data)}"