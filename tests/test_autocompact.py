"""Cycle 15 (loop2): auto-compaction in the agent loop.

Verify probe (plan.md): >=4 tests — trigger over budget, no-op under budget,
post-compaction system re-injection, registry-selected strategy honored.
"""

from __future__ import annotations

import pytest

from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext
from codemonkey.strategies.compaction import (
    SlidingWindowCompaction,
    SummarizingCompaction,
)


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class EchoProvider:
    """Records what it received; always answers 'ok'."""

    protocol = "openai"

    def __init__(self):
        self.seen = []

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.seen.append({"messages": list(messages), "system": system})
        return Turn("ok")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


def _big_history(n_msgs=12, chars=9000):
    return [{"role": "user" if i % 2 == 0 else "assistant",
             "content": f"msg{i} " + "x" * chars} for i in range(n_msgs)]


def test_triggers_when_over_budget(tmp_path):
    prov = EchoProvider()
    comp = SlidingWindowCompaction(keep=4)
    run_turns(
        prov, "final question", _ctx(tmp_path),
        tool_protocol="auto", max_turns=3,
        history=_big_history(12, 9000),            # ~27k tokens estimated
        context_limit=4000,                        # way under
        compaction=comp,
    )
    first = prov.seen[0]["messages"]
    # compacted: only the 4-keep window + this run's user prompt
    assert len(first) <= 5
    assert first[-1]["content"].startswith("final question")


def test_noop_when_under_budget(tmp_path):
    prov = EchoProvider()
    comp = SlidingWindowCompaction(keep=4)
    hist = [{"role": "user", "content": "tiny"}]
    run_turns(
        prov, "hello", _ctx(tmp_path),
        tool_protocol="auto", max_turns=3,
        history=hist, context_limit=32000, compaction=comp,
    )
    first = prov.seen[0]["messages"]
    assert len(first) == 2  # history + prompt, untouched


def test_post_compaction_system_prompt_still_sent(tmp_path):
    """Anti governance-decay: even after compaction the SYSTEM prompt rides
    every provider call."""
    prov = EchoProvider()
    comp = SlidingWindowCompaction(keep=3)
    run_turns(
        prov, "go", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=3,
        history=_big_history(14, 9000),
        context_limit=3000,
        compaction=comp,
        system_extra="You are codemonkey. Always answer.",
    )
    for call in prov.seen:
        assert "You are codemonkey." in call["system"]
        assert "You have tools." in call["system"]


def test_notice_event_emitted(tmp_path):
    prov = EchoProvider()
    events = []
    run_turns(
        prov, "go", _ctx(tmp_path),
        tool_protocol="auto", max_turns=3,
        history=_big_history(14, 9000),
        context_limit=3000,
        compaction=SlidingWindowCompaction(keep=3),
        on_event=events.append,
    )
    notices = [e for e in events if e.get("type") == "notice" and "auto-compaction" in e.get("message", "")]
    assert notices, f"expected a compaction notice, got: {events[:5]}"


def test_summarizing_strategy_via_registry_selection(tmp_path, monkeypatch):
    """The exec wiring selects via the registry; env Forces sliding-window."""
    from codemonkey.strategies import build

    monkeypatch.setenv("CODEMONKEY_STRATEGY_COMPACTION", "sliding-window")
    bundle = build({"context_limit": 32000})
    comp = bundle["compaction"]
    assert comp.name == "sliding-window"

    # registry default keep=10 (cfg knob: strategies.compaction_keep): feed 20
    # msgs so compaction definitely fires and yields <= 12 (marker + 10 + prompt)
    prov = EchoProvider()
    run_turns(
        prov, "go", _ctx(tmp_path),
        tool_protocol="auto", max_turns=3,
        history=_big_history(20, 9000),
        context_limit=3000,
        compaction=comp,
    )
    first = prov.seen[0]["messages"]
    assert len(first) <= 12
    assert any("prior context" in str(m.get("content", "")) for m in first)


def test_summarizing_uses_provider_gracefully(tmp_path):
    class SummarizingProvider(EchoProvider):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.seen.append({"messages": list(messages), "system": system})
            # summarization call: single user message asking for a brief
            if len(messages) == 1 and "Summarize" in str(messages[0].get("content", "")):
                return Turn("[prior context]\ndense brief of earlier work")
            return Turn("ok")

    prov = SummarizingProvider()
    comp = SummarizingCompaction(context_limit=3000)
    run_turns(
        prov, "go", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=3,
        history=_big_history(14, 9000),
        context_limit=3000,
        compaction=comp,
    )
    # call[0] is the summarizer request (single message); the NEXT provider
    # call is the compacted conversation and must carry the brief marker.
    assert len(prov.seen) >= 2
    conv = prov.seen[1]["messages"]
    assert len(conv) < 15  # compacted
    assert any("prior context" in str(m.get("content", "")) for m in conv)
    # ...and the real user prompt still present
    assert conv[-1]["content"] == "go"
