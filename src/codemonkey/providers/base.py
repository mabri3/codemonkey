"""Common types and the provider interface."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


class ProviderError(Exception):
    """Non-auth provider/transport error. Carries the HTTP status if known."""

    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status
        # 51F2: set once the message has been surfaced through the event
        # stream, so the CLI's catch-all doesn't print the same line twice.
        self.reported = False


class AuthError(ProviderError):
    """401/403 or missing-credential error (→ CLI exit 2)."""

    def __init__(self, message: str, status: Optional[int] = 401):
        super().__init__(message, status)


@dataclass
class ChatTurn:
    """A single model response.

    `tool_calls` carries native tool calls (provider `tool_calls` / `tool_use`
    blocks) when the provider surfaces them; the prompt protocol fills it from
    `parse_tool_calls(turn.content)`.
    """

    content: str = ""
    reasoning: str = ""
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    tool_calls: list = field(default_factory=list)


TokenSink = Optional[Callable[[str], None]]


class ProviderBase:
    """Unified chat interface over OpenAI- and Anthropic-style endpoints.

    `messages` is OpenAI-shaped: a list of {"role": "system"|"user"|"assistant",
    "content": str}. The `system` argument is an extra system prompt layered on
    top (Anthropic uses a dedicated `system` field; OpenAI prepends a system
    message).
    """

    protocol: str = "openai"

    def chat(
        self,
        messages: list,
        *,
        system: Optional[str] = None,
        stream: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[list] = None,
        on_token: TokenSink = None,
    ) -> ChatTurn:
        raise NotImplementedError

    def list_models(self) -> list[str]:
        raise NotImplementedError
