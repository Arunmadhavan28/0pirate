from typing import Any
import requests
from .base import LLMProvider
from ..config import settings


class QwenProvider(LLMProvider):
    name = "qwen"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.host = settings.ollama_host.rstrip("/")  # ensure no trailing slash
        self.model = model or "qwen2.5-coder:7b-instruct"

    def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Calls the Ollama /api/chat endpoint to run a Qwen model. This is the
        correct endpoint for modern instruction-tuned models.
        """
        model_to_use = model or self.model
        url = f"{self.host}/api/chat"

        payload = {
            "model": model_to_use,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            response = requests.post(url, json=payload, timeout=600)
            response.raise_for_status()
            result_data = response.json()

            # For the /api/chat endpoint, the response is in message.content
            return result_data.get("message", {}).get("content", "")

        except requests.exceptions.RequestException as e:
            error_message = f"Error calling Ollama at {self.host}: {e}"
            print(f"[QWEN_PROVIDER_ERROR] {error_message}")
            raise Exception(error_message) from e