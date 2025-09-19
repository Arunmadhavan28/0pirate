# src/utils/provider.py
from __future__ import annotations
import logging
import random
import time
from typing import Any, Dict, Optional

# Defaults
MAX_API_RETRIES: int = 5
BASE_API_DELAY: float = 1.0
MAX_BACKOFF: float = 30.0

logger = logging.getLogger(__name__)

class ProviderUnavailableError(Exception):
    """Raised when provider cannot fulfill request after retries."""

def _is_transient_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(t in s for t in ("429", "rate limit", "timeout", "temporarily", "unavailable"))

def call_provider_with_retry(
    provider: Any,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    temperature: float = 0.2,
    **kwargs: Any
) -> Any:
    """Call `provider.complete` with exponential backoff, jitter, and telemetry."""
    retries = max_retries or MAX_API_RETRIES
    attempt = 0
    last_exc: Optional[Exception] = None
    
    while attempt < retries:
        try:
            args: Dict[str, Any] = {**kwargs, "temperature": temperature}
            if timeout is not None:
                args["timeout"] = timeout
            return provider.complete(**args)
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1 and _is_transient_error(exc):
                delay = min(BASE_API_DELAY * (2 ** attempt), MAX_BACKOFF) + random.uniform(0, 1.0)
                time.sleep(delay)
                attempt += 1
                continue
            break
    raise ProviderUnavailableError(f"Provider '{getattr(provider, 'name', 'unknown')}' unavailable after {retries} attempts") from last_exc