"""Cycle 44 (loop12): exec --job injection + JOB_STEP write-back."""

from __future__ import annotations

import pytest

from codemonkey.jobs import create, load, set_step


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


def _run_exec(job_id, tmp_path, monkeypatch, assistant_reply="done. JOB_STEP step1 done -- all good"):
    """Run the real exec path with a stubbed loop (no live model)."""
    import codemonkey.exec as exec_mod
    import codemonkey.loop as loop_mod

    captured = {}

    def fake_run_turns(provider, prompt, ctx, **kw):
        captured["system_extra"] = kw.get("system_extra")
        captured["prompt"] = prompt
        turn = Turn(assistant_reply)
        turn.reasoning = ""
        turn.all_messages = [{"role": "user", "content": prompt},
                             {"role": "assistant", "content": assistant_reply}]
        return turn

    monkeypatch.setattr(loop_mod, "run_turns", fake_run_turns)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("x")

    code = exec_mod.run_exec("work on it", ephemeral=False, job_id=job_id,
                             skip_git_repo_check=True, stdin_cm="")
    return code, captured


def test_job_injection_and_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    job = create("ship it", ["step1", "step2"])
    code, cap = _run_exec(job["id"], tmp_path, monkeypatch)
    assert code == 0
    # goal + steps injected into the system context
    se = cap["system_extra"] or ""
    assert "ship it" in se and "step1" in se
    # marker persisted the transition
    assert load(job["id"])["steps"][0]["status"] == "done"
    assert load(job["id"])["steps"][0]["note"] == "all good"


def test_cross_run_resume_shows_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    job = create("multi-run", ["s1", "s2"])
    set_step(job["id"], "s1", "done", note="first run")
    code, cap = _run_exec(job["id"], tmp_path, monkeypatch,
                          assistant_reply="ok. JOB_STEP s2 done")
    se = cap["system_extra"] or ""
    assert "[x] s1 — first run" in se  # progress from the PREVIOUS run visible
    assert load(job["id"])["steps"][1]["status"] == "done"


def test_invalid_marker_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    job = create("g", ["s1"])
    _run_exec(job["id"], tmp_path, monkeypatch,
              assistant_reply="nothing here. JOB_STEP bogus-step done -- x")
    # unknown step id: no crash, no state change
    assert load(job["id"])["steps"][0]["status"] == "pending"


def test_unknown_job_id_errors(tmp_path, monkeypatch):
    import codemonkey.exec as exec_mod
    from codemonkey.exec import ExecUsageError

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("x")
    with pytest.raises(ExecUsageError, match="no such job"):
        exec_mod.run_exec("work", ephemeral=True, job_id="missing-job",
                          skip_git_repo_check=True, stdin_cm="")


def test_ephemeral_does_not_write(tmp_path, monkeypatch):
    from codemonkey.exec import ExecUsageError
    import codemonkey.exec as exec_mod
    import codemonkey.loop as loop_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    job = create("g", ["s1"])
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("x")

    def fake_run_turns(provider, prompt, ctx, **kw):
        t = Turn("ok. JOB_STEP s1 done")
        t.reasoning = ""
        t.all_messages = [{"role": "user", "content": prompt},
                          {"role": "assistant", "content": "ok. JOB_STEP s1 done"}]
        return t

    monkeypatch.setattr(loop_mod, "run_turns", fake_run_turns)
    exec_mod.run_exec("work", ephemeral=True, job_id=job["id"],
                      skip_git_repo_check=True, stdin_cm="")
    # ephemeral: no write-back
    assert load(job["id"])["steps"][0]["status"] == "pending"
