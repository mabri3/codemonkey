"""loop46 cycle 86 — the R-J revocation surface.

`revoke` must restore prior behavior IN ONE COMMAND (proven by a byte-diff on
the prompt a `skills=use` run actually sends), `disable` must stop every load
and every call WITHOUT deleting evidence, and every state change must land in
the journal. A revocation surface whose bite cannot be observed in the next
run's prompt is a promise, not a control.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from codemonkey import journal, skills
from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext


class Turn:
    def __init__(self, c):
        self.content = c
        self.usage = {}
        self.tool_calls = []


class Prov:
    protocol = "openai"

    def __init__(self):
        self.system = None

    def chat(self, messages, system=None, **kw):
        if self.system is None:
            self.system = system or ""
        return Turn("finished")


def _admit(tmp, name="demo_ok", tool_src=None, run_id="r-orig"):
    skills.write_manifest(tmp, {
        "name": name, "spec": "says hello",
        "params": {"type": "object", "properties": {}},
        "probe": "echo ok",
        "provenance": {"run_id": run_id, "session_id": "s1", "taint_free": True},
        "status": "quarantined",
    }, tool_src=tool_src or "def run(args, ctx):\n    return {'ok': True, 'output': 'ran'}\n")
    skills.set_status(tmp, name, "admitted", reason="C86 test setup")


def _prompt_for(tmp):
    prov = Prov()
    ctx = ToolContext(workdir=tmp, sandbox="workspace-write", timeout=30,
                      extra={"config": {"strategies": {"skills": "use"}}})
    run_turns(prov, "hi", ctx, tool_protocol="prompt", memory_enabled=False)
    return prov.system or ""


def _cli(tmp, *args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(
        [sys.executable, "-m", "codemonkey.cli", "skills", *args],
        cwd=str(tmp), capture_output=True, text=True, env=e)


def test_show_prints_provenance_and_history(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    _admit(tmp_path)
    r = _cli(tmp_path, "show", "demo_ok")
    assert r.returncode == 0, r.stderr
    assert "run_id=r-orig" in r.stdout          # the originating run id
    assert "probe:   echo ok" in r.stdout
    assert "admitted" in r.stdout
    assert "quarantined -> admitted" in r.stdout  # history rendered


def test_revoke_removes_in_one_command_and_bites_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    _admit(tmp_path)
    pre = _prompt_for(tmp_path)
    assert "demo_ok:" in pre                    # advertised before

    r = _cli(tmp_path, "revoke", "demo_ok")
    assert r.returncode == 0, r.stderr
    assert "revoked" in r.stdout
    assert skills.list_skills(tmp_path) == []   # gone from the store
    assert skills.load_admitted(tmp_path) == []

    post = _prompt_for(tmp_path)
    assert "demo_ok" not in post                # byte-diff: line gone
    recs = [x for x in journal.read_thread(skills.skill_thread(tmp_path))
            if x.get("type") == "skill.revoked"]
    assert recs and recs[-1]["key"] == "demo_ok"
    assert recs[-1]["status"] == "was-admitted"


def test_disable_zero_loads_evidence_kept_and_the_run_still_succeeds(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    _admit(tmp_path)
    r = _cli(tmp_path, "disable")
    assert r.returncode == 0, r.stderr
    assert "DISABLED" in r.stdout
    assert skills.load_admitted(tmp_path) == []     # zero skills loaded
    listed = skills.list_skills(tmp_path)           # evidence still on disk
    assert [x["name"] for x in listed] == ["demo_ok"]
    assert "demo_ok" not in _prompt_for(tmp_path)
    # the run still succeeds with zero skills
    prov = Prov()
    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=30,
                      extra={"config": {"strategies": {"skills": "use"}}})
    turn = run_turns(prov, "hi", ctx, tool_protocol="prompt", memory_enabled=False)
    assert turn.content == "finished"
    recs = [x for x in journal.read_thread(skills.skill_thread(tmp_path))
            if x.get("type") == "skills.disabled"]
    assert recs
    # reversible, and the reversal is journaled too
    r = _cli(tmp_path, "disable", "--enable")
    assert r.returncode == 0 and "ENABLED" in r.stdout
    assert [x["name"] for x in skills.load_admitted(tmp_path)] == ["demo_ok"]
    assert [x for x in journal.read_thread(skills.skill_thread(tmp_path))
            if x.get("type") == "skills.enabled"]


def test_disable_blocks_dispatch_not_just_advertising(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    _admit(tmp_path)
    assert skills.dispatch(tmp_path, "demo_ok", {})["ok"] is True
    skills.set_disabled(tmp_path, True, reason="test")
    res = skills.dispatch(tmp_path, "demo_ok", {})
    assert res["ok"] is False and "disabled" in res["error"]
    skills.set_disabled(tmp_path, False)
    assert skills.dispatch(tmp_path, "demo_ok", {})["ok"] is True


def test_unknown_names_are_refused_not_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    r = _cli(tmp_path, "revoke", "nope")
    assert r.returncode == 2
    assert "no skill named" in (r.stdout + r.stderr)
    r = _cli(tmp_path, "show", "nope")
    assert r.returncode == 2
