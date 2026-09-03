"""OpenAI-style chat-completions provider (llama.cpp, vLLM, OpenAI, any
OpenAI-compatible server). Raw httpx — no SDK.

Streaming uses the SSE wire format (`data: {...}` lines, `data: [DONE]`
terminator). Non-streaming is a single JSON body.
"""

from __future__ import annotations

import time
import json
from typing import Optional

import httpx

from .. import retry
from .base import (
    AuthError,
    ChatTurn,
    ProviderBase,
    ProviderError,
)






def _native_openai_tool_calls(tool_calls) -> list:
    """OpenAI `message.tool_calls` -> [{"name", "args"}, ...]."""
    out = []
    for tc in tool_calls or []:
        fn = tc.get("function") or {}
        raw = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            args = {"_raw": raw}
        out.append({"name": fn.get("name", ""), "args": args})
    return out


def _auth_headers(api_key: Optional[str]) -> dict:
    headers = {"Content-Type": "application/json"}
    # llama.cpp servers usually ignore auth; OpenAI-compatible gates need it.
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def parse_sse_events(text: str) -> list[dict]:
    """Parse an SSE stream body into data-payload dicts (skip heartbeats/comments)."""
    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


class OpenAIProvider(ProviderBase):
    protocol = "openai"

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None,
        timeout: float = 300.0,
        client: Optional[httpx.Client] = None,
        max_retries: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._client = client or httpx.Client(timeout=timeout)
        self.max_retries = max(0, int(max_retries))
        self._owns_client = client is None

    # -- low-level -----------------------------------------------------

    def _url(self, suffix: str) -> str:
        base = self.base_url
        if suffix.startswith("/"):
            # base_url may or may not already carry /v1
            return base + suffix if not base.endswith("v1") else base + suffix
        return f"{base}/{suffix}"

    def _request(self, path: str, body: dict) -> dict:
        url = self._url(path)
        attempts = retry.attempts_for(self.max_retries)
        last: ProviderError | None = None
        for attempt in range(1, attempts + 1):
            try:
                resp = self._client.post(url, json=body, headers=_auth_headers(self.api_key))
            except httpx.HTTPError as exc:
                last = ProviderError(f"transport error contacting {url}: {exc}")
                if retry.backoff_transport(attempt=attempt, attempts=attempts):
                    continue
                raise retry.annotate(last, attempt) from exc
            if resp.status_code in (401, 403):
                raise AuthError(
                    f"auth failed ({resp.status_code}) from {url}: {resp.text[:200]}",
                    status=resp.status_code,
                )
            if resp.status_code >= 400:
                text = resp.text[:300]
                last = ProviderError(
                    f"HTTP {resp.status_code} from {url}: {text}",
                    status=resp.status_code,
                )
                if retry.backoff_http(
                    attempt=attempt, attempts=attempts,
                    status=resp.status_code, text=text, headers=getattr(resp, "headers", None),
                ):
                    continue
                raise retry.annotate(last, attempt)
            return resp.json()
        raise retry.annotate(last or ProviderError(f"no response from {url}"), attempts)

    def _request_stream(self, path: str, body: dict) -> list[dict]:
        """Streaming request. Retries apply to the response STATUS only —
        once bytes have been handed to the caller a retry would duplicate
        tokens, so a mid-stream transport failure propagates."""
        url = self._url(path)
        body = dict(body)
        body["stream"] = True
        attempts = retry.attempts_for(self.max_retries)
        last: ProviderError | None = None
        # loop5-final: wall-clock cap on the WHOLE streamed response. The httpx
        # read timeout only fires on gaps BETWEEN bytes; a reasoning model that
        # trickles tokens never trips it (A9 hung 31+ min this way).
        stream_deadline = time.monotonic() + max(60.0, float(getattr(self, "timeout", 300.0)))
        for attempt in range(1, attempts + 1):
            started = False
            try:
                with self._client.stream(
                    "POST", url, json=body, headers=_auth_headers(self.api_key)
                ) as resp:
                    if resp.status_code in (401, 403):
                        resp.read()
                        raise AuthError(
                            f"auth failed ({resp.status_code}) from {url}: {resp.text[:200]}",
                            status=resp.status_code,
                        )
                    if resp.status_code >= 400:
                        resp.read()
                        text = resp.text[:300]
                        last = ProviderError(
                            f"HTTP {resp.status_code} from {url}: {text}",
                            status=resp.status_code,
                        )
                        if retry.backoff_http(
                            attempt=attempt, attempts=attempts,
                            status=resp.status_code, text=text, headers=getattr(resp, "headers", None),
                        ):
                            continue
                        raise retry.annotate(last, attempt)
                    started = True
                    events: list[dict] = []
                    for line in resp.iter_lines():
                        if time.monotonic() > stream_deadline:
                            raise ProviderError(
                                f"stream wall-clock deadline exceeded from {url} "
                                f"(>{max(60.0, float(getattr(self, 'timeout', 300.0))):.0f}s)"
                            )
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload = line[len("data:"):].strip()
                        if not payload or payload == "[DONE]":
                            continue
                        try:
                            events.append(json.loads(payload))
                        except json.JSONDecodeError:
                            continue
                    return events
            except httpx.HTTPError as exc:
                last = ProviderError(f"transport error contacting {url}: {exc}")
                if not started and retry.backoff_transport(
                    attempt=attempt, attempts=attempts
                ):
                    continue
                raise retry.annotate(last, attempt) from exc
        raise retry.annotate(last or ProviderError(f"no response from {url}"), attempts)

    # -- interface -----------------------------------------------------

    def _messages(self, messages: list, system: Optional[str]) -> list:
        msgs = [dict(m) for m in messages]
        if system:
            msgs.insert(0, {"role": "system", "content": system})
        return msgs

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
        cache_prompt: bool = True,
    ) -> ChatTurn:
        body: dict = {
            "model": self.model,
            "messages": self._messages(messages, system),
            "stream": bool(stream),
        }
        # llama.cpp KV-cache reuse: cache_prompt hints the server to reuse the
        # prefix over a stable system + earlier turns. Harmless/ignored by
        # servers that do not know the field.
        if cache_prompt:
            body["cache_prompt"] = True
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if temperature is not None:
            body["temperature"] = temperature
        if tools is not None:
            body["tools"] = tools
        if tools is not None and "tool_choice" not in body:
            body["tool_choice"] = "auto"

        if not stream:
            data = self._request("/chat/completions", body)
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            turn = ChatTurn(
                content=msg.get("content") or "",
                reasoning=(msg.get("reasoning") or msg.get("reasoning_content") or ""),
                finish_reason=choice.get("finish_reason") or "stop",
                usage=data.get("usage") or {},
            )
            turn.tool_calls = _native_openai_tool_calls(msg.get("tool_calls"))
            return turn

        # streaming
        turn = ChatTurn()
        tc_acc: dict = {}
        for event in self._request_stream("/chat/completions", body):
            choice = (event.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            piece = delta.get("content")
            if piece:
                turn.content += piece
                if on_token:
                    on_token(piece)
            r = delta.get("reasoning") or delta.get("reasoning_content")
            if r:
                turn.reasoning += r
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                slot = tc_acc.setdefault(idx, {"name": "", "arguments": ""})
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["arguments"] += fn["arguments"]
            if choice.get("finish_reason"):
                turn.finish_reason = choice["finish_reason"]
            if event.get("usage"):
                turn.usage = event["usage"]
        for idx in sorted(tc_acc):
            slot = tc_acc[idx]
            try:
                args = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {"_raw": slot["arguments"]}
            turn.tool_calls.append({"name": slot["name"], "args": args})
        return turn

    def list_models(self) -> list[str]:
        url = self._url("/models")
        try:
            resp = self._client.get(url, headers=_auth_headers(self.api_key))
        except httpx.HTTPError as exc:
            raise ProviderError(f"transport error contacting {url}: {exc}") from exc
        if resp.status_code in (401, 403):
            raise AuthError(
                f"auth failed ({resp.status_code}) from {url}", status=resp.status_code
            )
        if resp.status_code >= 400:
            raise ProviderError(
                f"HTTP {resp.status_code} from {url}: {resp.text[:300]}",
                status=resp.status_code,
            )
        data = resp.json()
        items = data.get("data", data if isinstance(data, list) else [])
        names: list[str] = []
        for item in items:
            if isinstance(item, dict):
                names.append(item.get("id", ""))
            else:
                names.append(str(item))
        return [n for n in names if n]

    def close(self) -> None:
        if self._owns_client:
            self._client.close()