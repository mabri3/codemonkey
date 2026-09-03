"""Cycle 41 (loop11): adversarial review rounds."""

from __future__ import annotations

import pytest

from codemonkey.sandbox import ToolContext
from codemonkey.tools.delegate import run


@pytest.fixture()
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)


class FakeProc:
    def __init__(self, stdout):
        self.returncode = 0
        self.stdout = stdout
        self.stderr = ""


def test_review_rounds_validation(ctx):
    res = run({"task": "x", "review_rounds": -1}, ctx)
    assert not res.ok
    res = run({"task": "x", "review_rounds": 9}, ctx)
    assert not res.ok
    assert "0..5" in res.output


def test_zero_rounds_is_current_behavior(ctx, monkeypatch):
    calls = {"n": 0}

    def fake_spawn(task_text, sandbox, ctx2):
        calls["n"] += 1
        return {"ok": True, "output": "done"}

    monkeypatch.setattr("codemonkey.tools.delegate._spawn", fake_spawn)
    res = run({"task": "do", "role": "implementer", "review_rounds": 0}, ctx)
    assert res.ok
    assert calls["n"] == 1  # only the implementer
    assert "review_rounds" not in res.meta


def test_critic_ok_stops_early(ctx, monkeypatch):
    """Round 1 critic says VERDICT: OK -> no fix round."""
    seq = []

    def fake_spawn(task_text, sandbox, ctx2):
        seq.append(task_text)
        if "[critic role]" in task_text:
            return {"ok": True, "output": "FINDINGS: none\nVERDICT: OK"}
        return {"ok": True, "output": "implementation v1"}

    monkeypatch.setattr("codemonkey.tools.delegate._spawn", fake_spawn)
    res = run({"task": "do", "review_rounds": 3}, ctx)
    assert res.ok
    assert res.meta["verdict"] == "OK"
    assert len(seq) == 2  # implementer + critic (no fix round)
    assert res.meta["review_rounds"][0]["verdict"] == "OK"


def test_changes_required_triggers_fix_round(ctx, monkeypatch):
    """Round 1 critic says CHANGES-REQUIRED -> implementer fix round runs."""
    seq = []

    def fake_spawn(task_text, sandbox, ctx2):
        seq.append(task_text)
        if "[critic role]" in task_text:
            return {"ok": True,
                    "output": "FINDINGS: 1. missing edge case\nVERDICT: CHANGES-REQUIRED"}
        if "Address these review findings" in task_text:
            return {"ok": True, "output": "implementation v2 (fixed)"}
        return {"ok": True, "output": "implementation v1"}

    monkeypatch.setattr("codemonkey.tools.delegate._spawn", fake_spawn)
    res = run({"task": "do", "review_rounds": 2}, ctx)
    assert res.ok
    assert len(seq) >= 3  # implementer + critic + fix (+ maybe critic 2)
    assert any("Address these review findings" in s for s in seq)
    assert any("missing edge case" in s for s in seq)  # findings fed to fix


def test_rounds_recorded_in_meta(ctx, monkeypatch):
    def fake_spawn(task_text, sandbox, ctx2):
        if "[critic role]" in task_text:
            return {"ok": True, "output": "VERDICT: OK"}
        return {"ok": True, "output": "impl"}

    monkeypatch.setattr("codemonkey.tools.delegate._spawn", fake_spawn)
    res = run({"task": "do", "review_rounds": 2}, ctx)
    rounds = res.meta["review_rounds"]
    assert rounds[0]["round"] == 1 and rounds[0]["verdict"] == "OK"
