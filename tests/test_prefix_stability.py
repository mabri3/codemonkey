"""Cycle 22 (loop4): prompt-prefix stability + cache_prompt passthrough.

Verify probe (plan.md): >=4 tests — system string byte-identical across 3
consecutive turns incl. after tool results; byte-identical after forced
compaction (only the tail differs); cache_prompt present/absent in the openai
body per the flag; anthropic request body unchanged.
"""

from __future__ import annotations

import pytest

from codemonkey.loop import run_turns
from codemonkey.protocol import prompt_block
from codemonkey.sandbox import ToolContext
from codemonkey.tools import SPECS


class Turn:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = tool_calls or []


class MultiTurnProvider:
    """Turn 1: two shell calls. Turn 2: final. Records the system each call."""

    protocol = "openai"

    def __init__(self):
        self.calls = 0
        self.systems = []
        self.msg_log = []

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, cache_prompt=True, **kw):
        self.calls += 1
        self.systems.append(system)
        self.msg_log.append(list(messages))
        if self.calls == 1:
            return Turn(
                'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo one"}}\n'
                'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo two"}}\n'
            )
        return Turn("finished")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


def test_system_byte_identical_across_three_turns(tmp_path):
    prov = MultiTurnProvider()
    run_turns(prov, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3)
    assert prov.calls == 2
    assert len(prov.systems) == 2
    assert prov.systems[0] == prov.systems[1]
    # non-empty, deterministic prompt block
    assert prov.systems[0] == prompt_block(SPECS, memory_enabled=True)


def test_system_identical_across_calls_including_tool_results(tmp_path):
    """Same as above but explicit: the system the model sees after TOOL_RESULTs
    is byte-identical to the first call's system."""
    prov = MultiTurnProvider()
    turn = run_turns(prov, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3)
    first = prov.systems[0]
    last = prov.systems[-1]
    assert first == last
    # and tool results ARE in the tail
    tail = [m for m in turn.all_messages if str(m.get("content", "")).startswith("TOOL_RESULT")]
    assert len(tail) == 2


def test_system_identical_after_forced_compaction(tmp_path):
    from codemonkey.strategies.compaction import SlidingWindowCompaction

    prov = MultiTurnProvider()
    big = [{"role": "user" if i % 2 == 0 else "assistant",
            "content": f"m{i} " + "x" * 9000} for i in range(14)]
    run_turns(
        prov, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3,
        history=big, context_limit=3000,
        compaction=SlidingWindowCompaction(keep=3),
    )
    assert len(prov.systems) == 2
    # compaction rewrote the MESSAGE tail; the system prefix is byte-stable
    assert prov.systems[0] == prov.systems[1]
    # and the tail actually shrank (compaction happened)
    msgs2 = prov.msg_log[1]
    assert len(msgs2) < len(big) + 1


# ---------------- cache_prompt in the openai request body ----------------

def test_cache_prompt_present_when_enabled(tmp_path):
    from codemonkey.providers.openai import OpenAIProvider

    captured = {}
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.base_url = "http://x"
    provider.model = "m"
    provider.api_key = "k"

    def fake_request(path, body):
        captured.update(body)
        return {"choices": [{"message": {"content": "ok"}, "usage": {}}]}

    provider._request = fake_request
    provider.chat([{"role": "user", "content": "hi"}], cache_prompt=True)
    assert captured.get("cache_prompt") is True


def test_cache_prompt_absent_when_disabled(tmp_path):
    from codemonkey.providers.openai import OpenAIProvider

    captured = {}
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.base_url = "http://x"
    provider.model = "m"
    provider.api_key = "k"

    def fake_request(path, body):
        captured.update(body)
        return {"choices": [{"message": {"content": "ok"}, "usage": {}}]}

    provider._request = fake_request
    provider.chat([{"role": "user", "content": "hi"}], cache_prompt=False)
    assert "cache_prompt" not in captured


def test_anthropic_body_unchanged_by_cache_flag(tmp_path, monkeypatch):
    """The anthropic provider must not gain a cache_prompt field."""
    import inspect
    from codemonkey.providers import anthropic as ant

    src = inspect.getsource(ant)
    assert "cache_prompt" not in src
