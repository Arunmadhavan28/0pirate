from __future__ import annotations
import importlib
import sys
from ..config import settings
from typing import Optional, Dict
from .base import LLMProvider

PROVIDER_MAP = {
    "ollama": "ollama_provider",
    "openai": "openai_provider",
    "anthropic": "anthropic_provider",
    "gemini": "gemini_provider",
    "deepseek": "deepseek_provider",
    "mistral": "mistral_provider",
    "qwen": "qwen_provider",
    "groq": "groq_provider",
}

def get_provider(provider_name: str, api_keys: Optional[Dict[str, str]] = None) -> LLMProvider:
    """
    Dynamically loads a provider. If an api_keys dict is passed, it's used for BYOK.
    If provider_name is 'auto', it uses server-side keys for selection.
    """
    # ADD THIS LINE to extract the key from the dictionary
    api_key = api_keys.get("api_key") if api_keys else None

    if provider_name == "auto":
        # This logic for server-side auto-selection remains unchanged
        if settings.google_key:
            return get_provider("gemini")
        elif settings.openai_key:
            return get_provider("openai")
        elif settings.anthropic_key:
            return get_provider("anthropic")
        # ... other auto-selection checks
        else:
            print("No cloud API key found, defaulting to Ollama.", file=sys.stderr)
            return get_provider("ollama")

    if provider_name not in PROVIDER_MAP:
        raise ValueError(f"Unsupported provider: {provider_name}")

    module_name = PROVIDER_MAP[provider_name]
    try:
        module = importlib.import_module(f".{module_name}", package="src.providers")
    except (ImportError, ModuleNotFoundError) as e:
        raise ValueError(f"Could not import provider module '{module_name}': {e}")

    ProviderClass = None
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and issubclass(attr, LLMProvider) and attr is not LLMProvider:
            ProviderClass = attr
            break
    
    if not ProviderClass:
        raise ValueError(f"Could not find LLMProvider class in module '{module_name}'")

    # This line now works because api_key is defined above
    return ProviderClass(api_key=api_key)