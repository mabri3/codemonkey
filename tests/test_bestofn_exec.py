"""Cycle 79 (loop 38): `exec --best-of N` with machine verification.

R-I entry-point probe: scripted real-exec runs (fake scripted provider,
attempt 1 writes the wrong file / attempt 2 the right one, verify command
checks the file) through the REAL run_exec — N attempts, zero-residue
workspace reset between candidates, first verifier-pass wins, honest
failure keeps the last evidence, `bestofn.*` events in the trace.
"""

from __future__ import annotations

import sys

import pytest

import codemonkey.exec as exec_mod
from codemonkey.exec import ExecUsageError, run_exec


class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


def _write_call(path, content):
    import json as _json
    args = _json.dumps({"path": path, "content": content})
    return 'TOOL_CALL: {"name": "write_file", "arguments": ' + args + '}\n'


class ScriptedProv:
    """Replays scripted contents across attempts (shared instance, so the
    script advances through attempt 1 into attempt 2)."""

    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n <= len(self.script):
            return Turn(self.script[self.n - 1])
        return Turn("finished")

    def close(self):
        pass


def _patched_run(monkeypatch, prov):
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    monkeypatch.setattr(exec_mod, "_provider_from_config", patched)


def _run(monkeypatch, tmp_path, prov, **kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    _patched_run(monkeypatch, prov)
    events: list = []
    params = dict(
        cwd=tmp_path,
        skip_git_repo_check=True,
        ephemeral=True,
        stream_deltas=False,
        stdin_cm="",
        sandbox="workspace-write",
        approval="never",
        event_sink=events,
    )
    params.update(kw)
    code = run_exec("write the answer file", **params)
    return code, events


def _verifier(target="RIGHT"):
    py = sys.executable
    return (f'"{py}" -c "import sys; sys.exit(0 if '
            f"open('answer.txt').read().strip()=={target!r} else 1)\"")


def _types(events, etype):
    return [e for e in events if e.get("type") == etype]


# ---------------- R-I: scripted real-exec runs ----------------

def test_second_attempt_wins(monkeypatch, tmp_path):
    """Attempt 1 writes WRONG (verifier fails), attempt 2 writes RIGHT:
    run ends exit 0, final tree carries the verified content."""
    prov = ScriptedProv([
        _write_call("answer.txt", "WRONG"), "attempt one done",
        _write_call("answer.txt", "RIGHT"), "attempt two done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov,
                        best_of=2, verify_command=_verifier())
    assert code == 0
    assert (tmp_path / "answer.txt").read_text() == "RIGHT"
    attempts = _types(events, "bestofn.attempt")
    assert [a["index"] for a in attempts] == [0, 1]
    done = _types(events, "bestofn.completed")
    assert len(done) == 1
    assert done[0]["ok"] is True and done[0]["index"] == 1


def test_byte_identity_reset(monkeypatch, tmp_path):
    """Files created by attempt 1 are ABSENT after the reset (full-tree
    reset, not checkpoint-group only)."""
    prov = ScriptedProv([
        _write_call("answer.txt", "WRONG") + _write_call("junk.txt", "residue"),
        "attempt one done",
        _write_call("answer.txt", "RIGHT"), "attempt two done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov,
                        best_of=2, verify_command=_verifier())
    assert code == 0
    assert not (tmp_path / "junk.txt").exists()
    assert (tmp_path / "answer.txt").read_text() == "RIGHT"


def test_honest_failure_keeps_last_evidence(monkeypatch, tmp_path):
    """No candidate passes: exit 1, last attempt's tree stands, completed
    carries ok=False with a null index."""
    prov = ScriptedProv([
        _write_call("answer.txt", "WRONG1"), "one",
        _write_call("answer.txt", "WRONG2"), "two",
    ])
    code, events = _run(monkeypatch, tmp_path, prov,
                        best_of=2, verify_command=_verifier())
    assert code == 1
    assert (tmp_path / "answer.txt").read_text() == "WRONG2"
    done = _types(events, "bestofn.completed")
    assert len(done) == 1
    assert done[0]["ok"] is False and done[0]["index"] is None


def test_default_off_emits_no_bestofn_events(monkeypatch, tmp_path):
    prov = ScriptedProv([_write_call("answer.txt", "solo"), "done"])
    code, events = _run(monkeypatch, tmp_path, prov)
    assert code == 0
    assert _types(events, "bestofn.attempt") == []
    assert _types(events, "bestofn.completed") == []
    assert (tmp_path / "answer.txt").read_text() == "solo"


# ---------------- usage probes ----------------

def test_best_of_without_verifier_is_usage_error(monkeypatch, tmp_path):
    """--best-of 2 with no verify command → ExecUsageError (CLI: exit 2)."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CODEMONKEY_VERIFY_COMMAND", raising=False)
    with pytest.raises(ExecUsageError, match="verify command"):
        run_exec("whatever", cwd=tmp_path, skip_git_repo_check=True,
                 ephemeral=True, stream_deltas=False, stdin_cm="",
                 best_of=2, verify_command="")


def test_best_of_with_dry_run_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(ExecUsageError, match="dry-run"):
        run_exec("whatever", cwd=tmp_path, skip_git_repo_check=True,
                 ephemeral=True, stream_deltas=False, stdin_cm="",
                 best_of=2, verify_command=_verifier(), dry_run=True)


# ---------------- snapshot unit ----------------

def test_snapshot_restore_byte_identity(tmp_path):
    from codemonkey.bestofn import restore_tree, snapshot_tree

    (tmp_path / "keep.txt").write_text("v1")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.txt").write_text("n")
    snap = snapshot_tree(tmp_path)
    (tmp_path / "keep.txt").write_text("MUTATED")
    (tmp_path / "new.txt").write_text("residue")
    (tmp_path / "sub" / "nested.txt").unlink()
    restore_tree(tmp_path, snap)
    assert (tmp_path / "keep.txt").read_text() == "v1"
    assert not (tmp_path / "new.txt").exists()
    assert (tmp_path / "sub" / "nested.txt").read_text() == "n"
