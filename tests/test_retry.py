"""Cycle 23 (loop4): provider retry/backoff with Retry-After + full jitter.

Verify probe (plan.md): >=6 tests — 429 with Retry-After sleeps that amount;
503 retries with increasing bounded jittered delays then succeeds; 400/404 not
retried; AuthError raises first attempt; tools-parameter 500 raises immediately
(no retry, fallback intact); max_retries exhausted -> ProviderError with count.
"""

from __future__ import annotations

import httpx
import pytest

from codemonkey.providers.openai import OpenAIProvider
from codemonkey.retry import parse_retry_after, should_retry, sleep_delay


class FakeClient:
    """Minimal httpx.Client stand-in with a scriptable .post."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def post(self, url, json=None, headers=None):
        self.calls += 1
        return self.script.pop(0)


def _provider(max_retries=3, script=None):
    p = OpenAIProvider.__new__(OpenAIProvider)
    p.base_url = "http://x/v1"
    p.model = "m"
    p.api_key = "k"
    p.max_retries = max_retries
    p._client = FakeClient(script or [])
    return p


class FakeResp:
    def __init__(self, status, text="", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}

    def json(self):
        return {"choices": [{"message": {"content": "ok"}, "usage": {}}]}


def test_429_with_retry_after_sleeps_that_amount(monkeypatch):
    p = _provider()
    sleeps = []
    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: sleeps.append(s))
    p._client.script = [FakeResp(429, "slow down", {"Retry-After": "2"}), FakeResp(200)]
    out = p._request("/chat/completions", {"model": "m"})
    assert out["choices"][0]["message"]["content"] == "ok"
    assert sleeps == [2.0]  # Retry-After honored exactly, no jitter


def test_503_retries_with_bounded_jitter_then_succeeds(monkeypatch):
    p = _provider(max_retries=3)
    delays = []
    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: delays.append(s))
    p._client.script = [FakeResp(503, "a"), FakeResp(503, "b"), FakeResp(200)]
    out = p._request("/chat/completions", {"model": "m"})
    assert out["choices"][0]["message"]["content"] == "ok"
    assert len(delays) == 2
    # bounded exponential windows with full jitter: 0<=d<=0.5 then 0<=d<=1.0
    assert 0 <= delays[0] <= 0.5
    assert 0 <= delays[1] <= 1.0


def test_400_404_not_retried(monkeypatch):
    p = _provider()
    p._client.script = [FakeResp(400, "nope"), FakeResp(404, "nope")]
    from codemonkey.providers.base import ProviderError

    with pytest.raises(ProviderError) as exc:
        p._request("/chat/completions", {"model": "m"})
    assert p._client.calls == 1  # first 400 raised immediately


def test_auth_error_never_retried(monkeypatch):
    from codemonkey.providers.base import AuthError

    p = _provider()
    p._client.script = [FakeResp(401, "bad key"), FakeResp(401, "bad key")]
    with pytest.raises(AuthError):
        p._request("/chat/completions", {"model": "m"})
    assert p._client.calls == 1


def test_tools_500_raises_immediately_no_retry(monkeypatch):
    """The llama.cpp tools-param 500 must propagate NOW so auto-fallback works."""
    p = _provider()
    p._client.script = [FakeResp(500, "error: unsupported tools parameter"), FakeResp(500, "x")]
    from codemonkey.providers.base import ProviderError

    with pytest.raises(ProviderError) as exc:
        p._request("/chat/completions", {"model": "m", "tools": []})
    assert p._client.calls == 1
    assert exc.value.status == 500
    # and the loop's rejection classifier still recognizes it
    from codemonkey.loop import looks_like_tools_rejection

    assert looks_like_tools_rejection(exc.value)


def test_non_tools_500_is_retried(monkeypatch):
    p = _provider(max_retries=2)
    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    p._client.script = [FakeResp(500, "internal error: transient"), FakeResp(200)]
    out = p._request("/chat/completions", {"model": "m"})
    assert out["choices"][0]["message"]["content"] == "ok"
    assert p._client.calls == 2


def test_max_retries_exhausted_error_mentions_attempts(monkeypatch):
    p = _provider(max_retries=2)  # 3 attempts total
    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    p._client.script = [FakeResp(503, "down")] * 5
    from codemonkey.providers.base import ProviderError

    with pytest.raises(ProviderError):
        p._request("/chat/completions", {"model": "m"})
    assert p._client.calls == 3  # 1 + 2 retries


def test_sleep_delay_full_jitter_bounds():
    for attempt in (1, 2, 3, 6):
        for _ in range(50):
            d = sleep_delay(attempt)
            cap = min(20.0, 0.5 * (2 ** (attempt - 1)))
            assert 0 <= d <= cap


def test_parse_retry_after():
    assert parse_retry_after("2") == 2.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("not-a-date") is None


# -- streaming path (the DEFAULT exec path: stream_deltas=True) ---------


class _StreamCtx:
    def __init__(self, resp):
        self.resp = resp

    def __enter__(self):
        return self.resp

    def __exit__(self, *a):
        return False


class FakeStreamResp(FakeResp):
    def __init__(self, status, text="", headers=None, lines=()):
        super().__init__(status, text, headers)
        self.lines = list(lines)

    def read(self):
        return self.text.encode()

    def close(self):
        pass

    def iter_lines(self):
        return iter(self.lines)


class FakeStreamClient(FakeClient):
    def stream(self, method, url, json=None, headers=None):
        self.calls += 1
        return _StreamCtx(self.script.pop(0))

    def build_request(self, method, url, json=None, headers=None):
        return ("req", url)

    def send(self, req, stream=False):
        self.calls += 1
        return self.script.pop(0)


def _stream_provider(max_retries=3, script=None):
    p = _provider(max_retries=max_retries)
    p._client = FakeStreamClient(script or [])
    return p


def test_stream_503_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    ok = FakeStreamResp(200, lines=['data: {"choices":[{"delta":{"content":"hi"}}]}',
                                    "data: [DONE]"])
    p = _stream_provider(script=[FakeStreamResp(503, "down"), ok])
    events = p._request_stream("/chat/completions", {"model": "m"})
    assert p._client.calls == 2
    assert events and events[0]["choices"][0]["delta"]["content"] == "hi"


def test_stream_tools_500_raises_immediately(monkeypatch):
    from codemonkey.loop import looks_like_tools_rejection
    from codemonkey.providers.base import ProviderError

    p = _stream_provider(script=[FakeStreamResp(500, "unsupported tools parameter")] * 3)
    with pytest.raises(ProviderError) as exc:
        p._request_stream("/chat/completions", {"model": "m", "tools": []})
    assert p._client.calls == 1
    assert looks_like_tools_rejection(exc.value)


def test_stream_auth_error_not_retried():
    from codemonkey.providers.base import AuthError

    p = _stream_provider(script=[FakeStreamResp(401, "bad key")] * 2)
    with pytest.raises(AuthError):
        p._request_stream("/chat/completions", {"model": "m"})
    assert p._client.calls == 1


# -- transport errors ---------------------------------------------------


class BoomClient(FakeClient):
    """Raises a transport error `fails` times, then serves the script."""

    def __init__(self, fails, script):
        super().__init__(script)
        self.fails = fails

    def post(self, url, json=None, headers=None):
        self.calls += 1
        if self.calls <= self.fails:
            raise httpx.ConnectError("connection reset")
        return self.script.pop(0)


def test_transport_error_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    p = _provider(max_retries=3)
    p._client = BoomClient(2, [FakeResp(200)])
    out = p._request("/chat/completions", {"model": "m"})
    assert out["choices"][0]["message"]["content"] == "ok"
    assert p._client.calls == 3


def test_transport_error_exhausted_reports_attempts(monkeypatch):
    from codemonkey.providers.base import ProviderError

    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    p = _provider(max_retries=1)
    p._client = BoomClient(5, [])
    with pytest.raises(ProviderError) as exc:
        p._request("/chat/completions", {"model": "m"})
    assert p._client.calls == 2
    assert "after 2 attempts" in str(exc.value)


def test_exhausted_http_error_reports_attempts(monkeypatch):
    from codemonkey.providers.base import ProviderError

    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    p = _provider(max_retries=2)
    p._client = FakeClient([FakeResp(503, "down")] * 3)
    with pytest.raises(ProviderError) as exc:
        p._request("/chat/completions", {"model": "m"})
    assert "after 3 attempts" in str(exc.value)
    assert exc.value.status == 503


# -- anthropic provider + factory wiring --------------------------------


def test_anthropic_post_retries_on_529(monkeypatch):
    from codemonkey.providers.anthropic import AnthropicProvider

    monkeypatch.setattr("codemonkey.retry.do_sleep", lambda s: None)
    p = AnthropicProvider(api_key="k", client=FakeClient(
        [FakeResp(529, "overloaded"), FakeResp(200)]
    ))
    kind, resp = p._post({"model": "m"})
    assert kind == "json" and resp.status_code == 200
    assert p._client.calls == 2


def test_anthropic_400_not_retried():
    from codemonkey.providers.anthropic import AnthropicProvider
    from codemonkey.providers.base import ProviderError

    p = AnthropicProvider(api_key="k", client=FakeClient([FakeResp(400, "bad")] * 2))
    with pytest.raises(ProviderError):
        p._post({"model": "m"})
    assert p._client.calls == 1


def test_max_retries_reaches_both_providers():
    from codemonkey.providers import build_provider

    o = build_provider("openai", "http://x/v1", "m", max_retries=7)
    a = build_provider("anthropic", "http://y", "m", api_key="k", max_retries=7)
    assert o.max_retries == 7 and a.max_retries == 7
    assert build_provider("openai", "http://x/v1", "m", max_retries=-4).max_retries == 0


def test_config_default_and_env_override(monkeypatch):
    from codemonkey.config import load_config

    monkeypatch.setenv("CODEMONKEY_MAX_RETRIES", "5")
    cfg = load_config()
    assert int(cfg["max_retries"]) == 5
