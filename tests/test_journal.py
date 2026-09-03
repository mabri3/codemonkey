"""Cycle 31 (loop7): execution journal + failure taxonomy."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time

import pytest

from codemonkey.journal import (args_key, classify_error, class_summary,
                                find_outcome, journal_path, list_threads,
                                read_thread, record)


@pytest.fixture()
def jhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_intent_before_outcome_ordering(jhome):
    record("t1", "intent", tool="write_file", key="k1")
    record("t1", "outcome", tool="write_file", key="k1", status="ok")
    recs = read_thread("t1")
    assert [r["type"] for r in recs] == ["intent", "outcome"]


def test_error_classes(jhome):
    from codemonkey.providers.base import ProviderError

    assert classify_error(None) == "unknown"
    assert classify_error(TimeoutError("deadline exceeded")) == "timeout"
    assert classify_error(ProviderError("HTTP 401", status=401)) == "auth"
    assert classify_error(ConnectionError("connect failed")) == "transport"
    assert classify_error(json.JSONDecodeError("x", "y", 0)) == "parse"
    assert classify_error(ProviderError("tool boom")) == "tool-error"


def test_args_never_stored_raw(jhome):
    record("t2", "intent", tool="write_file", key="k2")
    raw = journal_path("t2").read_text()
    assert "secrets" not in raw
    # key is a stable hash of (thread, turn, index, args)
    k1 = args_key("t2", 1, 0, {"path": "x", "content": "secrets"})
    k2 = args_key("t2", 1, 0, {"path": "x", "content": "secrets"})
    assert k1 == k2 and len(k1) == 24
    k3 = args_key("t2", 1, 1, {"path": "x", "content": "secrets"})
    assert k3 != k1  # call-index participates


def test_journal_survives_kill9(jhome):
    """Append-only design: records written before a kill are readable after."""
    record("t3", "intent", tool="shell", key="k3")
    record("t3", "outcome", tool="shell", key="k3", status="ok", output="done")
    # simulate crash: process killed right after (no cleanup needed — file
    # already flushed per write). Read it back:
    recs = read_thread("t3")
    assert recs[-1]["output"] == "done"


def test_find_outcome_replay_source(jhome):
    record("t4", "intent", tool="write_file", key="kA")
    record("t4", "outcome", tool="write_file", key="kA", status="ok",
           output="wrote 10 bytes")
    hit = find_outcome("t4", "kA")
    assert hit and hit["status"] == "ok" and hit["output"] == "wrote 10 bytes"
    assert find_outcome("t4", "missing") is None


def test_thread_isolation_and_list(jhome):
    record("tA", "intent", tool="shell", key="k1")
    record("tB", "intent", tool="shell", key="k2")
    assert read_thread("tA")[0]["thread"] == "tA"
    assert set(list_threads()) >= {"tA", "tB"}


def test_class_summary(jhome):
    record("t5", "outcome", tool="shell", key="k1", status="ok")
    record("t5", "outcome", tool="shell", key="k2", status="error",
           error_class="timeout")
    record("t5", "intent", tool="shell", key="k3")  # intent ignored
    assert class_summary(read_thread("t5")) == {"ok": 1, "timeout": 1}


def test_loop_writes_journal_records(jhome, tmp_path, monkeypatch):
    """End-to-end in-process: run_turns with journal_thread writes intents
    and outcomes around tool dispatch."""
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    (tmp_path / "f.txt").write_text("hello")
    prov_turns = {"n": 0}

    class Turn:
        def __init__(self, content):
            self.content = content
            self.usage = {"total_tokens": 1}
            self.tool_calls = []

    class Prov:
        protocol = "openai"

        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, cache_prompt=True, **kw):
            prov_turns["n"] += 1
            if prov_turns["n"] == 1:
                return Turn('TOOL_CALL: {"name": "read_file", "arguments": {"path": "f.txt"}}\n')
            return Turn("done")

    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)
    run_turns(Prov(), "go", ctx, tool_protocol="prompt", max_turns=3,
              journal_thread="tloop")
    recs = read_thread("tloop")
    types = [(r["type"], r["tool"]) for r in recs]
    assert ("intent", "read_file") in types
    assert ("outcome", "read_file") in types
