"""Cycle 32 (loop7): idempotent mutating tools.

Verify probe (plan.md): >=5 tests — key stability, replay-on-hit returns
recorded result, miss executes, read-only tools unaffected, replay recorded
in journal.
"""

from __future__ import annotations

import json

import pytest

from codemonkey.journal import (args_key, find_outcome, journal_path, read_thread,
                                record)
from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext


@pytest.fixture()
def jhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class ToolCallProv:
    """Turn 1: write_file call. Turn 2+: final. Counts dispatches via fs."""

    def __init__(self, calls):
        self.calls = list(calls)
        self.n = 0

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, cache_prompt=True, **kw):
        self.n += 1
        if self.n <= len(self.calls):
            return Turn(self.calls[self.n - 1])
        return Turn("finished")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


def test_replay_on_hit(tmp_path, jhome):
    """Second run with the same thread + same call: journal outcome replayed,
    dispatch NOT re-executed (file mtime unchanged)."""
    f = tmp_path / "data.txt"
    f.write_text("v1")

    prov = ToolCallProv([
        'TOOL_CALL: {"name": "write_file", "arguments": {"path": "data.txt", "content": "v2"}}\n',
    ])
    run_turns(prov, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3,
              journal_thread="tid")
    assert f.read_text() == "v2"
    mtime1 = f.stat().st_mtime_ns

    # second run: same thread, same call -> replay
    prov2 = ToolCallProv([
        'TOOL_CALL: {"name": "write_file", "arguments": {"path": "data.txt", "content": "v2"}}\n',
    ])
    turn2 = run_turns(prov2, "go again", _ctx(tmp_path), tool_protocol="prompt",
                      max_turns=3, journal_thread="tid")
    assert f.stat().st_mtime_ns == mtime1  # NOT re-executed
    # the replayed output reached the model as a tool result
    recs = read_thread("tid")
    assert any(r.get("status") == "replayed" for r in recs)


def test_miss_executes(tmp_path, jhome):
    (tmp_path / "a.txt").write_text("x")
    prov = ToolCallProv([
        'TOOL_CALL: {"name": "write_file", "arguments": {"path": "a.txt", "content": "y"}}\n',
    ])
    run_turns(prov, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3,
              journal_thread="t-miss")
    assert (tmp_path / "a.txt").read_text() == "y"  # executed for real


def test_readonly_tools_not_replayed(tmp_path, jhome):
    (tmp_path / "f.txt").write_text("content")
    prov = ToolCallProv([
        'TOOL_CALL: {"name": "read_file", "arguments": {"path": "f.txt"}}\n',
    ])
    run_turns(prov, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3,
              journal_thread="t-ro")
    # read twice with the same thread: both dispatches execute (no replay)
    prov2 = ToolCallProv([
        'TOOL_CALL: {"name": "read_file", "arguments": {"path": "f.txt"}}\n',
    ])
    run_turns(prov2, "go", _ctx(tmp_path), tool_protocol="prompt", max_turns=3,
              journal_thread="t-ro")
    recs = read_thread("t-ro")
    intents = [r for r in recs if r["type"] == "intent" and r["tool"] == "read_file"]
    replays = [r for r in recs if r.get("status") == "replayed"]
    assert len(intents) >= 2  # executed both times
    assert not replays


def test_key_stability_and_distinction():
    a1 = args_key("t", 1, 0, {"path": "x", "content": "abc"})
    a2 = args_key("t", 1, 0, {"content": "abc", "path": "x"})  # order-independent
    assert a1 == a2
    assert args_key("t", 1, 0, {"path": "x", "content": "abd"}) != a1


def test_replay_recorded_in_journal(tmp_path, jhome):
    (tmp_path / "d.txt").write_text("1")
    call = 'TOOL_CALL: {"name": "write_file", "arguments": {"path": "d.txt", "content": "2"}}\n'
    run_turns(ToolCallProv([call]), "go", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=3, journal_thread="t-rec")
    run_turns(ToolCallProv([call]), "go", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=3, journal_thread="t-rec")
    recs = read_thread("t-rec")
    outcomes = [r for r in recs if r["type"] == "outcome" and r["tool"] == "write_file"]
    statuses = [r["status"] for r in outcomes]
    assert statuses.count("ok") >= 1 and statuses.count("replayed") >= 1
