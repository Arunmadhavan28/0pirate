from typing import Any, Dict
import requests
from .base import LLMProvider
from ..config import settings

class OllamaProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.host = settings.ollama_host.rstrip("/")
        # The default model can be mistral; it will be overridden by the frontend selection.
        self.model = model or "mistral"

    def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Intelligently calls the correct Ollama endpoint based on the model name.
        - Uses /api/chat for chat/instruct models (like qwen).
        - Uses /api/generate for base models (like mistral).
        """
        model_to_use = model or self.model
        
        # --- The logic to switch endpoints based on the selected model ---
        if "qwen" in model_to_use:
            # Use the modern /api/chat for Qwen
            url = f"{self.host}/api/chat"
            payload = {
                "model": model_to_use,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }
        else:
            # Use the original /api/generate for Mistral and other base models
            url = f"{self.host}/api/generate"
            payload = {
                "model": model_to_use,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            }

        try:
            response = requests.post(url, json=payload, timeout=6000)
            response.raise_for_status()
            result_data = response.json()

            # --- Parse the response based on the endpoint that was used ---
            if "qwen" in model_to_use:
                return result_data.get("message", {}).get("content", "")
            else:
                return result_data.get("response", "")

        except requests.exceptions.RequestException as e:
            error_message = f"Error calling Ollama at {self.host}: {e}"
            print(f"[OLLAMA_PROVIDER_ERROR] {error_message}")
            raise Exception(error_message) from e