"""Provider factory: pick the right implementation from a provider config block."""

from __future__ import annotations

from typing import Optional

from .base import (
    ChatTurn,
    ProviderBase,
    ProviderError,
    AuthError,
)
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider


def build_provider(
    protocol: str,
    base_url: str,
    model: str,
    api_key: Optional[str] = None,
    timeout: float = 300.0,
    client=None,
    max_retries: int = 3,
) -> ProviderBase:
    proto = (protocol or "openai").lower()
    kwargs = dict(
        base_url=base_url, model=model, api_key=api_key,
        timeout=timeout, client=client, max_retries=max_retries,
    )
    if proto == "openai":
        return OpenAIProvider(**kwargs)
    if proto == "anthropic":
        return AnthropicProvider(**kwargs)
    raise ValueError(f"unknown protocol '{protocol}' (openai | anthropic)")


__all__ = [
    "ProviderBase",
    "ProviderError",
    "AuthError",
    "ChatTurn",
    "OpenAIProvider",
    "AnthropicProvider",
    "build_provider",
]
