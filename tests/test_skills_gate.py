"""loop46 cycle 83 — the admission gate: exit code decides, never a model.

Every test here attacks the same claim from a different side: promotion is a
mechanical question (the candidate's self-probe ran and returned 0), the
verdict is journaled with the probe's real output, and the gate cannot be
widened by the thing it is supposed to quarantine. The discriminating cases —
a sandbox that forbids the probe, a probe that hangs, an admitted skill whose
evidence later fails — are the ones a rubber-stamp gate would pass green.
"""

from __future__ import annotations

import json
import os

from codemonkey import journal, skills


def _skill(tmp_path, name: str, probe: str, **over) -> None:
    man = {
        "name": name,
        "spec": "gate test candidate",
        "params": {"type": "object", "properties": {}},
        "probe": probe,
        "provenance": {"run_id": "run-gate", "session_id": "th-gate",
                       "taint_free": True},
        "status": "quarantined",
    }
    man.update(over)
    skills.write_manifest(tmp_path, man, tool_src="# candidate\n")


def _journal_records(tmp_path) -> list[dict]:
    return journal.read_thread(skills.skill_thread(tmp_path))


def test_probe_pass_promotes_and_journals(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _skill(tmp_path, "demo_ok", "echo gate_ok")
    res = skills.admit(tmp_path, "demo_ok", level="workspace-write")
    assert res["ok"] is True
    assert res["status"] == "admitted"
    assert res["probe_exit"] == 0
    assert skills.read_manifest(tmp_path, "demo_ok")["status"] == "admitted"
    assert len(skills.load_admitted(tmp_path)) == 1
    recs = _journal_records(tmp_path)
    admitted = [r for r in recs if r["type"] == "skill.admitted"]
    assert len(admitted) == 1
    assert admitted[0]["key"] == "demo_ok"
    assert admitted[0]["status"] == "probe_exit:0"
    assert "gate_ok" in admitted[0]["output"]


def test_probe_failure_stays_quarantined_and_records_the_stderr(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _skill(tmp_path, "demo_bad", "echo womp >&2; exit 3")
    res = skills.admit(tmp_path, "demo_bad", level="workspace-write")
    assert res["ok"] is False
    assert res["probe_exit"] == 3
    assert res["status"] == "quarantined"
    assert skills.read_manifest(tmp_path, "demo_bad")["status"] == "quarantined"
    assert skills.load_admitted(tmp_path) == []
    refused = [r for r in _journal_records(tmp_path)
               if r["type"] == "skill.refused"]
    assert len(refused) == 1
    assert refused[0]["status"] == "probe_exit:3"
    assert "womp" in refused[0]["output"]          # the ACTUAL stderr, not prose


def test_probe_cannot_escalate_the_sandbox_level(tmp_path, monkeypatch):
    """At a level that cannot run shell, the gate refuses — and the probe
    must not have executed (no side effect on disk)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _skill(tmp_path, "demo_escape", "touch pwned.txt")
    res = skills.admit(tmp_path, "demo_escape", level="read-only")
    assert res["ok"] is False
    assert res["probe_exit"] is None
    assert "sandbox refuses" in res["reason"]
    assert res["status"] == "quarantined"
    assert not (tmp_path / "pwned.txt").exists()   # it never ran
    refused = [r for r in _journal_records(tmp_path)
               if r["type"] == "skill.refused"]
    assert refused and refused[0]["status"] == "probe_exit:sandbox"


def test_probe_timeout_is_a_failure_not_a_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _skill(tmp_path, "demo_slow", "sleep 5")
    res = skills.admit(tmp_path, "demo_slow", level="workspace-write",
                       timeout=0.4)
    assert res["ok"] is False
    assert res["probe_exit"] == "timeout"
    assert res["status"] == "quarantined"
    assert skills.load_admitted(tmp_path) == []


def test_admitted_skill_is_evicted_when_its_probe_now_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    _skill(tmp_path, "demo_decay", "true")
    assert skills.admit(tmp_path, "demo_decay", level="workspace-write")["ok"]
    assert len(skills.load_admitted(tmp_path)) == 1
    # The evidence changes (hand-edited probe — the store's threat model).
    mpath = tmp_path / skills.STORE_DIR / "demo_decay" / "manifest.json"
    man = json.loads(mpath.read_text())
    man["probe"] = "false"
    mpath.write_text(json.dumps(man))
    res = skills.admit(tmp_path, "demo_decay", level="workspace-write")
    assert res["ok"] is False
    assert res["status"] == "evicted"
    assert skills.load_admitted(tmp_path) == []    # R-A: not loaded anymore
    assert [r for r in _journal_records(tmp_path)
            if r["type"] == "skill.evicted"]


def test_gate_never_consults_a_model(tmp_path, monkeypatch):
    """A model endpoint that cannot answer must not change the verdict — the
    gate has no provider on its path, and this pins that property."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("CODEMONKEY_MODEL", "does-not-exist")
    _skill(tmp_path, "demo_offline", "echo offline_ok")
    res = skills.admit(tmp_path, "demo_offline", level="workspace-write")
    assert res["ok"] is True and res["status"] == "admitted"


def test_unknown_level_and_missing_skill_are_usage_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    import pytest

    with pytest.raises(skills.SkillError):
        skills.admit(tmp_path, "nope", level="workspace-write")
    _skill(tmp_path, "demo_lvl", "true")
    with pytest.raises(skills.SkillError):
        skills.admit(tmp_path, "demo_lvl", level="god-mode")
