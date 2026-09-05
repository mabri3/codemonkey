"""Cycle 101 (loop 43): subprocess contract — versioned envelope + exit codes.

Every event crossing the exec boundary carries v==1 (stamped at the single
funnel, not at 40 emission sites). Exit codes follow build/contract.md.
"""

from __future__ import annotations

import pytest

import codemonkey.exec as exec_mod
from codemonkey.events import SCHEMA_V, stamp


class _Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


class _OkProv:
    protocol = "prompt"

    def chat(self, messages, system=None, **kw):
        return _Turn("done")

    def close(self):
        pass


class _StuckProv:
    """Same denied write every turn (approval=never) → gave-up, exit 3."""
    protocol = "prompt"

    def chat(self, messages, system=None, **kw):
        return _Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                     '{"path": "/tmp/cm101-denied.txt", "content": "x"}}\n')

    def close(self):
        pass


def _run(tmp_path, monkeypatch, prov, **kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    code = exec_mod.run_exec(
        "do it", cwd=tmp_path, skip_git_repo_check=True, ephemeral=True,
        stream_deltas=False, stdin_cm="", sandbox="workspace-write",
        event_sink=events, max_turns=kw.pop("max_turns", 12), **kw)
    return code, events


def test_all_events_versioned(tmp_path, monkeypatch):
    code, events = _run(tmp_path, monkeypatch, _OkProv())
    assert code == 0
    assert events, "a run must emit events"
    bare = [e for e in events if e.get("v") != SCHEMA_V]
    assert not bare, f"{len(bare)} unversioned events"
    types = {e.get("type") for e in events}
    assert {"thread.started", "turn.completed"} <= types


def test_gave_up_exit_3_with_versioned_report(tmp_path, monkeypatch):
    code, events = _run(tmp_path, monkeypatch, _StuckProv(),
                        approval="never")
    assert code == 3, f"gave-up must exit 3, got {code}"
    gave = [e for e in events if e.get("type") == "failure_report.gave_up"]
    # by design (91F4): loop report + exec's translated copy w/ thread_id
    assert len(gave) == 2, [e.get("report", {}).keys() for e in gave]
    assert {("thread_id" in e) for e in gave} == {True, False}
    assert all(e["v"] == SCHEMA_V for e in gave)


def test_usage_error_raises_not_returns(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(exec_mod.ExecUsageError):
        exec_mod.run_exec("", cwd=tmp_path, skip_git_repo_check=True,
                          stdin_cm="")
    # CLI maps ExecUsageError → exit 2 (contract §1); pinned at CLI level
    # by the conformance suite (C102), not here.


def test_stamp_never_clobbers():
    assert stamp({"type": "x", "v": 9})["v"] == 9
    assert stamp({"type": "x"})["v"] == SCHEMA_V


def test_contract_doc_exists():
    from pathlib import Path

    doc = Path(__file__).parent.parent / "build" / "contract.md"
    text = doc.read_text()
    for needle in ["| 0 |", "| 1 |", "| 2 |", "| 3 |", "`v: 1`",
                   "R43", "NOT decided here"]:
        assert needle in text, needle
