from __future__ import annotations
import os, requests, json
from typing import Optional, Dict, Any
from .base import LLMProvider
from ..config import settings

class DeepseekProvider(LLMProvider):
    name = "deepseek"

    def __init__(self, api_key: str | None = None):
        """Initialize the provider with a specific API key or fall back to settings."""
        self.api_key = api_key or settings.deepseek_key

    def complete(self, prompt: str, model: str | None = None, **kwargs) -> str:
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set.")
        
        model = model or "deepseek-chat"
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}", 
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get('temperature', 0.2),
        }
        
        if 'max_tokens' in kwargs:
            payload['max_tokens'] = kwargs['max_tokens']
        
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def chat_completion(self, messages: list[dict], model: Optional[str] = None, **kwargs) -> str:
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set.")
        
        model = model or "deepseek-chat"
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}", 
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get('temperature', 0.2),
        }
        
        if 'max_tokens' in kwargs:
            payload['max_tokens'] = kwargs['max_tokens']
        
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

    def stream_complete(self, prompt: str, model: Optional[str] = None, **kwargs):
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set.")
        
        model = model or "deepseek-chat"
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}", 
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get('temperature', 0.2),
            "stream": True
        }
        
        if 'max_tokens' in kwargs:
            payload['max_tokens'] = kwargs['max_tokens']
        
        response = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data)
                        if 'choices' in chunk and chunk['choices']:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue