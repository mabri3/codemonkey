"""Anthropic Messages-API provider (Claude). Raw httpx — no SDK.

Streaming uses Anthropic SSE events; text arrives as `content_block_delta`
with `delta.type == "text_delta"`. Non-streaming returns a `content` array of
blocks. Auth via `x-api-key` + `anthropic-version` headers.
"""

from __future__ import annotations

import json
from typing import Optional

import httpx

from .base import AuthError, ChatTurn, ProviderBase, ProviderError

ANTHROPIC_VERSION = "2023-06-01"


def _headers(api_key: str) -> dict:
    if not api_key:
        raise AuthError("anthropic provider requires an API key", status=None)
    return {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "Content-Type": "application/json",
    }


class AnthropicProvider(ProviderBase):
    protocol = "anthropic"

    def __init__(
        self,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-5",
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    def _messages(self, messages: list, system: Optional[str]) -> tuple[list, Optional[str]]:
        """Split system out; Anthropic uses a dedicated `system` field.

        In-prompt `system` messages come first (primary), then the extra
        `system` argument is appended, so ordering is deterministic.
        """
        sys_parts: list[str] = []
        msgs = []
        for m in messages:
            if m.get("role") == "system":
                sys_parts.append(m.get("content", ""))
            else:
                msgs.append({"role": m["role"], "content": m.get("content", "")})
        if system:
            sys_parts.append(system)
        return msgs, ("".join(sys_parts) if sys_parts else None)

    def _body(
        self,
        messages: list,
        system: Optional[str],
        stream: bool,
        max_tokens: Optional[int],
        temperature: Optional[float],
        tools: Optional[list],
    ) -> dict:
        msgs, sys_field = self._messages(messages, system)
        body: dict = {
            "model": self.model,
            "messages": msgs,
            "stream": bool(stream),
        }
        if sys_field:
            body["system"] = sys_field
        body["max_tokens"] = max_tokens if max_tokens is not None else 8192
        if temperature is not None:
            body["temperature"] = temperature
        if tools is not None:
            body["tools"] = tools
        return body

    def _post(self, body: dict, stream: bool = False):
        url = f"{self.base_url}/v1/messages"
        headers = _headers(self.api_key)
        try:
            if stream:
                req = self._client.build_request(
                    "POST", url, json=body, headers=headers
                )
                resp = self._client.send(req, stream=True)
                if resp.status_code in (401, 403):
                    resp.read()
                    raise AuthError(
                        f"auth failed ({resp.status_code}) from {url}: {resp.read()[:200]}",
                        status=resp.status_code,
                    )
                if resp.status_code >= 400:
                    resp.read()
                    raise ProviderError(
                        f"HTTP {resp.status_code} from {url}: {resp.read()[:300]}",
                        status=resp.status_code,
                    )
                return ("stream", resp)
            resp = self._client.post(url, json=body, headers=headers)
            if resp.status_code in (401, 403):
                raise AuthError(
                    f"auth failed ({resp.status_code}) from {url}: {resp.text[:200]}",
                    status=resp.status_code,
                )
            if resp.status_code >= 400:
                raise ProviderError(
                    f"HTTP {resp.status_code} from {url}: {resp.text[:300]}",
                    status=resp.status_code,
                )
            return ("json", resp)
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error contacting {url}: {exc}") from exc

    @staticmethod
    def _block_text(block: dict) -> str:
        btype = block.get("type")
        if btype == "text":
            return block.get("text", "")
        if btype == "thinking":
            return block.get("thinking", "")
        return ""

    def _extract(self, data: dict) -> ChatTurn:
        turn = ChatTurn()
        for block in data.get("content", []):
            if block.get("type") == "text":
                turn.content += block.get("text", "")
            elif block.get("type") == "thinking":
                turn.reasoning += block.get("thinking", "")
            elif block.get("type") == "tool_use":
                turn.tool_calls.append(
                    {"name": block.get("name", ""), "args": block.get("input") or {}}
                )
        turn.finish_reason = data.get("stop_reason") or "end_turn"
        usage = data.get("usage") or {}
        turn.usage = {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
        }
        return turn

    def chat(
        self,
        messages: list,
        *,
        system: Optional[str] = None,
        stream: bool = False,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        tools: Optional[list] = None,
        on_token=None,
    ) -> ChatTurn:
        body = self._body(messages, system, stream, max_tokens, temperature, tools)
        kind, resp = self._post(body, stream=stream)
        if kind == "json":
            return self._extract(resp.json())

        # streaming: parse SSE events
        turn = ChatTurn()
        tool_raw: dict = {}   # block index -> accumulated input JSON
        block_index: dict = {}  # block index -> position in turn.tool_calls
        for line in resp.iter_lines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "content_block_start":
                block = event.get("content_block") or {}
                idx = event.get("index")
                if block.get("type") == "tool_use":
                    turn.tool_calls.append(
                        {"name": block.get("name", ""), "args": {}}
                    )
                    if idx is not None:
                        block_index[idx] = len(turn.tool_calls) - 1
                        tool_raw[idx] = ""
            elif etype == "content_block_stop":
                idx = event.get("index")
                if idx is not None and idx in tool_raw:
                    raw = tool_raw[idx]
                    pos = block_index[idx]
                    try:
                        turn.tool_calls[pos]["args"] = json.loads(raw or "{}")
                    except json.JSONDecodeError:
                        turn.tool_calls[pos]["args"] = {"_raw": raw}
            elif etype == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "input_json_delta":
                    idx = event.get("index")
                    if idx is not None and idx in tool_raw:
                        tool_raw[idx] += delta.get("partial_json", "")
                elif delta.get("type") == "text_delta":
                    piece = delta.get("text", "")
                    turn.content += piece
                    if on_token:
                        on_token(piece)
                elif delta.get("type") == "thinking_delta":
                    turn.reasoning += delta.get("thinking", "")
            elif etype == "message_delta":
                delta = event.get("delta") or {}
                if delta.get("stop_reason"):
                    turn.finish_reason = delta["stop_reason"]
                if event.get("usage"):
                    u = event["usage"]
                    turn.usage["completion_tokens"] = u.get("output_tokens", 0)
            elif etype == "message_start":
                u = (event.get("message") or {}).get("usage") or {}
                turn.usage["prompt_tokens"] = u.get("input_tokens", 0)
        resp.close()
        return turn

    def list_models(self) -> list[str]:
        """Anthropic has no live models-list endpoint on most deployments;
        fall back to the configured model so `codemonkey models` still reports
        something usable."""
        return [self.model]

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
