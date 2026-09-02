"""Provider-layer tests. All HTTP is mocked (no live network).

Covers the cycle-2 verify probe:
  - openai: streaming SSE + non-streaming
  - anthropic: streaming (content_block_delta) + non-streaming
  - auth headers (openai Bearer, anthropic x-api-key)
  - 401 -> AuthError (-> CLI exit 2)
  - factory selection + unknown protocol
"""

from __future__ import annotations

import json

import pytest

from codemonkey.providers import (
    AnthropicProvider,
    AuthError,
    OpenAIProvider,
    ProviderError,
    build_provider,
)
from codemonkey.providers.base import ChatTurn


# ---------------------------------------------------------------- fakes

class FakeResp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code = status
        self._body = body
        self.text = text

    def json(self):
        return self._body

    def read(self):
        return self.text

    def iter_lines(self):
        return self.text.splitlines()

    def close(self):
        pass


class FakeStream:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self._resp

    def __exit__(self, *exc):
        return False


class FakeClient:
    """Duck-typed stand-in for httpx.Client for both stream and non-stream."""

    def __init__(self, responses=None, stream_text="", headers_capture=None):
        self.responses = responses or {}
        self.stream_text = stream_text
        self.headers_capture = headers_capture
        self.last_headers = None
        self.last_body = None
        self.timeout = 5.0

    def post(self, url, json=None, headers=None):
        self.last_headers = headers
        self.last_body = json
        r = self.responses.get(url, FakeResp(200, {}))
        return r

    def stream(self, method, url, json=None, headers=None):
        self.last_headers = headers
        self.last_body = json
        # stream endpoint returns SSE text
        return FakeStream(FakeResp(200, None, text=self.stream_text))

    def get(self, url, headers=None):
        self.last_headers = headers
        return self.responses.get(url, FakeResp(200, {"data": []}))

    def build_request(self, *a, **k):
        return object()

    def send(self, req, stream=False):
        return FakeResp(200, None, text=self.stream_text)

    def close(self):
        pass


def oai_sse() -> str:
    """A realistic OpenAI streaming SSE body."""
    def d(obj):
        return f"data: {json.dumps(obj)}"
    return "\n".join(
        [
            d({"choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}),
            d({"choices": [{"index": 0, "delta": {"content": "Hel"}, "finish_reason": None}]}),
            d({"choices": [{"index": 0, "delta": {"content": "lo!"}, "finish_reason": None}]}),
            d({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}),
            "data: [DONE]",
        ]
    ) + "\n"


# ---------------------------------------------------------------- openai

def test_openai_non_streaming():
    body = {"choices": [{"message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    client = FakeClient(responses={"http://llm:8080/v1/chat/completions": FakeResp(200, body)})
    p = OpenAIProvider("http://llm:8080/v1", "m", api_key="k", client=client)
    turn = p.chat([{"role": "user", "content": "ping"}])
    assert turn.content == "pong"
    assert turn.finish_reason == "stop"
    assert turn.usage.get("prompt_tokens") == 1
    # auth header present when key given
    assert client.last_headers.get("Authorization") == "Bearer k"


def test_openai_streaming_sse():
    client = FakeClient(stream_text=oai_sse())
    p = OpenAIProvider("http://llm:8080/v1", "m", client=client)
    got = []
    turn = p.chat([{"role": "user", "content": "hi"}], stream=True, on_token=got.append)
    assert turn.content == "Hello!"
    assert got == ["Hel", "lo!"]
    assert turn.finish_reason == "stop"
    assert turn.usage.get("completion_tokens") == 2


def test_openai_auth_401_raises_autherror():
    client = FakeClient(responses={"http://llm:8080/v1/chat/completions": FakeResp(401, None, text="unauthorized")})
    p = OpenAIProvider("http://llm:8080/v1", "m", api_key="bad", client=client)
    with pytest.raises(AuthError):
        p.chat([{"role": "user", "content": "x"}])


def test_openai_http_500_raises_provider_error():
    client = FakeClient(responses={"http://llm:8080/v1/chat/completions": FakeResp(500, None, text="parse error on tools")})
    p = OpenAIProvider("http://llm:8080/v1", "m", client=client)
    with pytest.raises(ProviderError) as ei:
        p.chat([{"role": "user", "content": "x"}])
    assert ei.value.status == 500


def test_openai_system_prompt_prepended():
    client = FakeClient(responses={"http://llm:8080/v1/chat/completions": FakeResp(200, {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})})
    p = OpenAIProvider("http://llm:8080/v1", "m", client=client)
    p.chat([{"role": "user", "content": "q"}], system="be terse")
    msgs = client.last_body["messages"]
    assert msgs[0] == {"role": "system", "content": "be terse"}
    assert msgs[1]["role"] == "user"


def test_openai_list_models():
    client = FakeClient(responses={"http://llm:8080/v1/models": FakeResp(200, {"data": [{"id": "Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf"}, {"id": "other"}]})})
    p = OpenAIProvider("http://llm:8080/v1", "m", client=client)
    assert p.list_models() == ["Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf", "other"]


# ---------------------------------------------------------------- anthropic

def anth_sse() -> str:
    def e(obj):
        return f"data: {json.dumps(obj)}"
    return "\n".join(
        [
            e({"type": "message_start", "message": {"usage": {"input_tokens": 5}}}),
            e({"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
            e({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Bon"}}),
            e({"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "jour"}}),
            e({"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 4}}),
        ]
    ) + "\n"


def test_anthropic_non_streaming():
    body = {
        "content": [
            {"type": "thinking", "thinking": "let me think"},
            {"type": "text", "text": "Bonjour"},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 7, "output_tokens": 3},
    }
    client = FakeClient(responses={"https://api.anthropic.com/v1/messages": FakeResp(200, body)})
    p = AnthropicProvider("https://api.anthropic.com", "claude-sonnet-4-5", api_key="sk-ant", client=client)
    turn = p.chat([{"role": "user", "content": "hi"}])
    assert turn.content == "Bonjour"
    assert turn.reasoning == "let me think"
    assert turn.finish_reason == "end_turn"
    assert client.last_headers["x-api-key"] == "sk-ant"
    assert client.last_headers["anthropic-version"]


def test_anthropic_streaming():
    client = FakeClient(stream_text=anth_sse())
    p = AnthropicProvider("https://api.anthropic.com", "claude-sonnet-4-5", api_key="sk-ant", client=client)
    got = []
    turn = p.chat([{"role": "user", "content": "hi"}], stream=True, on_token=got.append)
    assert turn.content == "Bonjour"
    assert got == ["Bon", "jour"]
    assert turn.finish_reason == "end_turn"


def test_anthropic_system_split():
    client = FakeClient(responses={"https://api.anthropic.com/v1/messages": FakeResp(200, {"content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}})})
    p = AnthropicProvider("https://api.anthropic.com", "m", api_key="k", client=client)
    p.chat([{"role": "system", "content": "sys1"}, {"role": "user", "content": "q"}], system="sys2")
    assert client.last_body["system"] == "sys1sys2"
    assert all(m["role"] != "system" for m in client.last_body["messages"])


def test_anthropic_missing_key_raises():
    p = AnthropicProvider("https://api.anthropic.com", "m", api_key=None, client=FakeClient())
    with pytest.raises(AuthError):
        p.chat([{"role": "user", "content": "x"}])


# ---------------------------------------------------------------- factory

def test_factory_openai_and_anthropic():
    assert build_provider("openai", "http://x", "m", client=FakeClient()).protocol == "openai"
    assert build_provider("anthropic", "http://x", "m", client=FakeClient()).protocol == "anthropic"
    assert build_provider("OPENAI", "http://x", "m", client=FakeClient()).protocol == "openai"


def test_factory_unknown_protocol():
    with pytest.raises(ValueError):
        build_provider("mistral", "http://x", "m")


def test_chatturn_defaults():
    t = ChatTurn()
    assert t.content == "" and t.finish_reason == "stop" and t.usage == {}
