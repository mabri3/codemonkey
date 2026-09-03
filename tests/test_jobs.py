"""Cycle 43 (loop12): durable jobs module + CLI."""

from __future__ import annotations

import json
import os

import pytest

from codemonkey.jobs import (create, job_path, list_jobs, load, render,
                             set_step)


@pytest.fixture()
def jhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_create_and_show(jhome):
    job = create("ship the feature", ["design", "build", "test"])
    loaded = load(job["id"])
    assert loaded["goal"] == "ship the feature"
    assert [s["id"] for s in loaded["steps"]] == ["design", "build", "test"]
    assert all(s["status"] == "pending" for s in loaded["steps"])
    text = render(loaded)
    assert "ship the feature" in text and "[ ] design" in text


def test_step_transitions(jhome):
    job = create("g", ["a", "b"])
    updated = set_step(job["id"], "a", "done", note="went fine")
    assert updated["steps"][0]["status"] == "done"
    assert updated["steps"][0]["note"] == "went fine"
    # persisted
    assert load(job["id"])["steps"][0]["status"] == "done"


def test_atomic_write_survives_crash(jhome):
    """Atomicity: tmp+replace means the job file is never partially written.
    Simulate: create, then write garbage to the .tmp (crash mid-write) — the
    real job file must still load."""
    job = create("g", ["s1"])
    p = job_path(job["id"])
    p.with_suffix(".tmp").write_text('{"id": "corrupt')
    assert load(job["id"])["goal"] == "g"  # real file unaffected
    # and a subsequent save overwrites the stale tmp cleanly
    set_step(job["id"], "s1", "done")
    assert load(job["id"])["steps"][0]["status"] == "done"


def test_list_jobs_sorted(jhome):
    import time as _t
    j1 = create("first", ["s"])
    _t.sleep(0.02)
    j2 = create("second", ["s"])
    jobs = list_jobs()
    assert [j["id"] for j in jobs] == [j1["id"], j2["id"]]


def test_done_and_fail_statuses(jhome):
    job = create("g", ["a", "b"])
    set_step(job["id"], "a", "done")
    set_step(job["id"], "b", "failed", note="blew up")
    loaded = load(job["id"])
    assert loaded["steps"][0]["status"] == "done"
    assert loaded["steps"][1] == {"id": "b", "status": "failed", "note": "blew up"}
    text = render(loaded)
    assert "[x] a" in text and "[!] b" in text


def test_unknown_job_step_bad_status(jhome):
    job = create("g", ["a"])
    assert set_step("nope", "a", "done") is None
    assert set_step(job["id"], "nope", "done") is None
    assert set_step(job["id"], "a", "bogus") is None


def test_cli_jobs_flow(jhome, monkeypatch):
    repo = "/Users/bharris/Programs/CodeMonkey"
    monkeypatch.chdir(repo)
    r1 = subprocess_run(["jobs", "create", "test goal", "step1,step2"], repo)
    assert "created" in r1.stdout
    jid = r1.stdout.split()[1]
    r2 = subprocess_run(["jobs", "done", jid, "step1", "--note", "ok"], repo)
    assert r2.returncode == 0
    r3 = subprocess_run(["jobs", "show", jid], repo)
    assert "[x] step1 — ok" in r3.stdout
    r4 = subprocess_run(["jobs", "list"], repo)
    assert jid in r4.stdout


def subprocess_run(args, cwd):
    import subprocess
    return subprocess.run(["uv", "run", "codemonkey"] + args,
                          capture_output=True, text=True, timeout=120, cwd=cwd)
