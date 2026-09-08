from __future__ import annotations
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    name: str = "base"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    @abstractmethod
    def complete(self, prompt: str, model: str | None = None, **kwargs) -> str:
        """
        The core method for an LLM provider.

        Args:
            prompt: The input prompt for the LLM.
            model: The specific model to use (optional).
            **kwargs: A dictionary for additional provider-specific parameters
                      like 'temperature', 'max_tokens', etc.
        """
        ...
