"""Cycle 9: REPL — slash commands, piped mode, reasoning stripping.

Live verify probe (requires provider): printf 'Reply with exactly: fig\\n/quit\\n'
| codemonkey -> exit 0, stdout contains fig. Mocked tests here cover the rest.
"""

from __future__ import annotations

import io

import pytest

from codemonkey.repl import ReplState, handle_slash, run_repl, strip_reasoning


# ---------------- slash commands ----------------

def test_slash_quit():
    state = ReplState("local", "m")
    assert handle_slash(state, "/quit", stderr=io.StringIO()) == "quit"
    assert handle_slash(state, "/exit", stderr=io.StringIO()) == "quit"


def test_slash_clear_empties_history():
    state = ReplState("local", "m")
    state.history = [{"role": "user", "content": "x"}]
    err = io.StringIO()
    assert handle_slash(state, "/clear", stderr=err) == "handled"
    assert state.history == []
    assert "cleared" in err.getvalue()


def test_slash_model_and_provider():
    state = ReplState("unblock2", "kimi-k2.7-code")
    err = io.StringIO()
    assert handle_slash(state, "/model", stderr=err) == "handled"
    assert "kimi-k2.7-code" in err.getvalue()
    err = io.StringIO()
    assert handle_slash(state, "/provider", stderr=err) == "handled"
    assert "unblock2" in err.getvalue()


def test_slash_usage_counts():
    state = ReplState("local", "m")
    state.usage["turns"] = 3
    state.usage["total_tokens"] = 420
    err = io.StringIO()
    assert handle_slash(state, "/usage", stderr=err) == "handled"
    assert "turns: 3" in err.getvalue()
    assert "420" in err.getvalue()


def test_slash_sessions_lists_or_empty():
    state = ReplState("local", "m")
    err = io.StringIO()
    # must not raise whether or not sessions exist
    assert handle_slash(state, "/sessions", stderr=err) == "handled"


def test_slash_help_lists_commands():
    state = ReplState("local", "m")
    err = io.StringIO()
    handle_slash(state, "/help", stderr=err)
    for cmd in ("/quit", "/clear", "/model", "/provider", "/usage", "/sessions"):
        assert cmd in err.getvalue()


def test_non_slash_falls_through_to_chat():
    state = ReplState("local", "m")
    assert handle_slash(state, "hello there", stderr=io.StringIO()) == "chat"


# ---------------- reasoning stripping ----------------

def test_strip_reasoning_removes_think_blocks():
    content = "<think>secret chain of thought</think>The answer is 42."
    assert strip_reasoning(content) == "The answer is 42."


def test_strip_reasoning_keeps_plain_content():
    assert strip_reasoning("just an answer") == "just an answer"


# ---------------- piped REPL end-to-end (mock provider) ----------------

class FakeTurn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 9}
        self.tool_calls = []


class FakeProvider:
    protocol = "openai"

    def __init__(self):
        self.calls = 0

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.calls += 1
        if on_token:
            on_token("fig")
        return FakeTurn("fig")

    def close(self):
        pass


def _cfg_with(monkeypatch, provider):
    return {"default_provider": "fake", "providers": {"fake": provider}}


def test_piped_repl_streams_final_to_stdout(tmp_path, monkeypatch):
    import codemonkey.repl as repl_mod

    provider = FakeProvider()
    monkeypatch.setattr(repl_mod, "_build_provider", lambda cfg, name: provider)

    cfg = _cfg_with({"protocol": "openai", "base_url": "http://x", "model": "m"}, None)
    cfg = {"default_provider": "fake", "providers": {"fake": {"protocol": "openai"}}}

    err = io.StringIO()
    out = io.StringIO()

    class FakeStdin:
        def isatty(self):
            return False

        def __iter__(self):
            return iter(["Reply with exactly: fig\n", "/quit\n"])

    import sys as _sys
    old_stdin = _sys.stdin
    _sys.stdin = FakeStdin()
    try:
        code = run_repl(cfg, stderr=err, stdout=out, stdin=_sys.stdin)
    finally:
        _sys.stdin = old_stdin

    assert code == 0
    assert "fig" in out.getvalue()
    # slash-command + provider banner chatter goes to stderr, not stdout
    assert "fig" not in err.getvalue() or "fig" in out.getvalue()


class FakeTty:
    def isatty(self):
        return False


def test_piped_repl_slash_only_is_silent_ok(tmp_path, monkeypatch):
    import codemonkey.repl as repl_mod

    provider = FakeProvider()
    monkeypatch.setattr(repl_mod, "_build_provider", lambda cfg, name: provider)

    cfg = {"default_provider": "fake", "providers": {"fake": {}}}
    err = io.StringIO()
    out = io.StringIO()

    class FakeStdin:
        def isatty(self):
            return False

        def __iter__(self):
            return iter(["/usage\n", "/quit\n"])

    import sys as _sys
    old = _sys.stdin
    _sys.stdin = FakeStdin()
    try:
        code = run_repl(cfg, stderr=err, stdout=out)
    finally:
        _sys.stdin = old

    assert code == 0
    assert "turns: 0" in err.getvalue()


def test_piped_repl_provider_error_continues(tmp_path, monkeypatch):
    """A provider error on one line must not kill the whole piped session."""
    import codemonkey.repl as repl_mod
    from codemonkey.providers.base import ProviderError

    class FlakyProvider(FakeProvider):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls == 1:
                raise ProviderError("503 overloaded", status=503)
            return FakeTurn("second ok")

    provider = FlakyProvider()
    monkeypatch.setattr(repl_mod, "_build_provider", lambda cfg, name: provider)

    cfg = {"default_provider": "fake", "providers": {"fake": {}}}
    err = io.StringIO()
    out = io.StringIO()

    class FakeStdin:
        def isatty(self):
            return False

        def __iter__(self):
            return iter(["first line", "second line", "/quit\n"])

    import sys as _sys
    old = _sys.stdin
    _sys.stdin = FakeStdin()
    try:
        code = run_repl(cfg, stderr=err, stdout=out)
    finally:
        _sys.stdin = old

    assert code == 0
    assert "provider error" in err.getvalue()
    assert "second ok" in out.getvalue()
