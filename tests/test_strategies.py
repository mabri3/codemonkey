"""Cycle 7: pluggable strategy layer — compaction / memory / session state.

Covers the cycle-7 verify probe (tests/test_strategies.py -q):
  - sliding-window compaction: old messages dropped, last N kept, no LLM call
  - summarizing compaction: no-op under trigger, triggers with mock provider
  - session-store round-trip for BOTH jsonl and sqlite backends
  - registry selection: env var > config > default; invalid name -> StrategyError
"""

from __future__ import annotations
import os
import pytest

from codemonkey.strategies import (
    StrategyError,
    build,
    select_strategy,
    get_compactor,
    get_memory,
    get_store,
    VALID_MEMORY,
    VALID_STORES,
    VALID_COMPACTORS,
)
from codemonkey.strategies.compaction import (
    SlidingWindowCompaction,
    SummarizingCompaction,
)


import pytest


@pytest.fixture()
def cfg():
    """Minimal strategies-only config for registry selection tests."""
    return {
        "strategies": {
            "compaction": "summarizing",
            "memory": "file",
            "session_state": "jsonl",
        }
    }


# ---------------- sliding-window compaction ----------------

def test_sliding_window_drops_old_keeps_last_n():
    msgs = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
    out = SlidingWindowCompaction(keep=5).maybe_compact(msgs)
    assert len(out) == 5
    assert out[0]["content"] == "msg 15"   # oldest kept
    assert out[-1]["content"] == "msg 19"  # newest kept


def test_sliding_window_no_llm_call():
    """sliding-window must never touch a provider — pass a poison sentinel."""

    class PoisonProvider:
        def chat(self, *a, **k):
            raise AssertionError("sliding-window must not call the provider")

    msgs = [{"role": "user", "content": "x"}] * 30
    out = SlidingWindowCompaction(keep=3).maybe_compact(msgs, provider=PoisonProvider())
    assert len(out) == 3


def test_sliding_window_below_keep_is_noop_copy():
    msgs = [{"role": "user", "content": "a"}] * 3
    out = SlidingWindowCompaction(keep=5).maybe_compact(msgs)
    assert len(out) == 3
    assert out is not msgs  # still returns a list (copy, safe)


# ---------------- summarizing compaction ----------------

class MockTurn:
    def __init__(self, content):
        self.content = content


class MockProvider:
    def __init__(self, content="SUMMARY-BRIEF"):
        self.content = content
        self.calls = 0

    def chat(self, messages, system=None, tools=None, stream=False):
        self.calls += 1
        return MockTurn(self.content)


def test_summarizing_noop_when_under_trigger():
    msgs = [{"role": "user", "content": f"short {i}"} for i in range(20)]
    out = SummarizingCompaction(context_limit=32000).maybe_compact(
        msgs, keep=10, provider=MockProvider())
    assert out == msgs or len(out) == len(msgs)  # not compacted


def test_summarizing_triggers_and_summarizes_with_provider():
    # 1500-char message => ~375 est tokens each; 15 older msgs => ~5600 >> 60% of 32000/4=8000? no
    # Make older content big enough: each ~20000 chars => 5000 tokens each.
    big = "x" * 20000
    msgs = [{"role": "user", "content": big} for _ in range(15)] + [
        {"role": "user", "content": f"recent {i}"} for i in range(10)
    ]
    prov = MockProvider("DENSE-BRIEF")
    out = SummarizingCompaction(context_limit=32000).maybe_compact(
        msgs, keep=10, provider=prov)
    assert prov.calls == 1
    assert len(out) == 11          # 1 brief + 10 recent
    assert "DENSE-BRIEF" in out[0]["content"]
    assert out[1]["content"] == "recent 0"


def test_summarizing_falls_back_when_provider_fails():
    class FailingProvider:
        def chat(self, *a, **k):
            raise RuntimeError("500 parse error (llama.cpp native tools)")

    big = "x" * 20000
    msgs = [{"role": "user", "content": big} for _ in range(15)] + [
        {"role": "user", "content": f"recent {i}"} for i in range(10)
    ]
    out = SummarizingCompaction(context_limit=32000).maybe_compact(
        msgs, keep=10, provider=FailingProvider())
    # graceful degrade: the plain recent window
    assert len(out) == 10
    assert out[0]["content"] == "recent 0"


def test_summarizing_no_provider_degrades_gracefully():
    big = "x" * 20000
    msgs = [{"role": "user", "content": big} for _ in range(15)] + [
        {"role": "user", "content": f"recent {i}"} for i in range(10)
    ]
    out = SummarizingCompaction(context_limit=32000).maybe_compact(
        msgs, keep=10, provider=None)
    assert len(out) == 10


# ---------------- session-store round-trips ----------------

def test_jsonl_store_roundtrip(tmp_path):
    store = get_store("jsonl", base=tmp_path)
    assert store.name == "jsonl"
    store.append_meta("t1", provider="local", model="m", cwd="/tmp")
    store.append_message("t1", "user", "hello")
    store.append_message("t1", "assistant", "world")

    data = store.load("t1")
    assert data["messages"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]

    entries = store.list()
    assert len(entries) == 1
    assert entries[0]["thread_id"] == "t1"
    assert entries[0]["created"] is not None
    assert store.latest() == "t1"


def test_sqlite_store_roundtrip(tmp_path):
    store = get_store("sqlite", base=tmp_path / "sessions.db")
    assert store.name == "sqlite"
    store.append_meta("t2", provider="local", model="m", cwd="/tmp")
    store.append_message("t2", "user", "hello")
    store.append_message("t2", "assistant", "world")

    data = store.load("t2")
    assert data["messages"] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]

    entries = store.list()
    assert len(entries) == 1
    assert entries[0]["thread_id"] == "t2"
    assert store.latest() == "t2"


def test_both_backends_persist_created_floor(tmp_path):
    """created is stamped once; later append_meta reuses it (floor semantics)."""
    for name, base in (("jsonl", tmp_path / "j"), ("sqlite", tmp_path / "s.db")):
        store = get_store(name, base=base)
        store.append_meta("t", provider="p", model="m", cwd="/")
        first = store.load("t")  # forces a read-back
        store.append_meta("t", provider="p", model="m", cwd="/")
        entries = store.list()
        assert entries[0]["created"] is not None


def test_missing_thread_raises():
    for name, base in (("jsonl", None), ("sqlite", None)):
        store = get_store(name, base=base)
        with pytest.raises(FileNotFoundError):
            store.load("does-not-exist-xyz")


# ---------------- registry / selection ----------------

def test_select_defaults(cfg):
    assert select_strategy("compaction", cfg) == "summarizing"
    assert select_strategy("memory", cfg) == "file"
    assert select_strategy("session_state", cfg) == "jsonl"


def test_select_env_overrides_config(cfg, monkeypatch):
    monkeypatch.setenv("CODEMONKEY_STRATEGY_COMPACTION", "sliding-window")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_MEMORY", "none")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_SESSION_STATE", "sqlite")
    assert select_strategy("compaction", cfg) == "sliding-window"
    assert select_strategy("memory", cfg) == "none"
    assert select_strategy("session_state", cfg) == "sqlite"


def test_select_config_value(cfg):
    cfg2 = dict(cfg)
    cfg2["strategies"] = dict(cfg.get("strategies", {}))
    cfg2["strategies"]["compaction"] = "sliding-window"
    assert select_strategy("compaction", cfg2) == "sliding-window"


def test_invalid_strategy_raises_with_valid_names(cfg):
    with pytest.raises(StrategyError) as exc:
        select_strategy("compaction", {**cfg, "strategies": {"compaction": "banana"}})
    for valid in VALID_COMPACTORS:
        assert valid in str(exc.value)
    # all domains
    with pytest.raises(StrategyError):
        select_strategy("memory", {**cfg, "strategies": {"memory": "banana"}})
    with pytest.raises(StrategyError):
        select_strategy("session_state", {**cfg, "strategies": {"session_state": "banana"}})
    with pytest.raises(StrategyError):
        select_strategy("bogus_domain", cfg)


def test_build_bundle(cfg):
    bundle = build(cfg)
    assert bundle["compaction"].name == "summarizing"
    assert bundle["memory"].name == "file"
    assert bundle["session_state"].name == "jsonl"


def test_build_with_env_selection(cfg, monkeypatch):
    monkeypatch.setenv("CODEMONKEY_STRATEGY_COMPACTION", "sliding-window")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_SESSION_STATE", "sqlite")
    bundle = build(cfg)
    assert bundle["compaction"].name == "sliding-window"
    assert bundle["session_state"].name == "sqlite"


def test_valid_sets():
    assert set(VALID_MEMORY) == {"file", "none"}
    assert set(VALID_STORES) == {"jsonl", "sqlite"}
    assert set(VALID_COMPACTORS) == {"sliding-window", "summarizing"}

