"""Cycle 33 (loop7): journal forensics CLI."""

from __future__ import annotations

import json
import subprocess

import pytest

from codemonkey.journal import class_summary, list_threads, record, read_thread


@pytest.fixture()
def jhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_list_threads(jhome):
    record("tA", "intent", tool="shell", key="k1")
    record("tB", "intent", tool="shell", key="k2")
    assert set(list_threads()) >= {"tA", "tB"}


def test_tail_shape(jhome):
    for i in range(5):
        record("tT", "outcome", tool="shell", key=f"k{i}", status="ok")
    recs = read_thread("tT")
    assert len(recs) == 5
    # tail semantics: last N
    assert recs[-1]["key"] == "k4"


def test_class_summary_counts(jhome):
    record("tC", "outcome", tool="shell", key="k1", status="ok")
    record("tC", "outcome", tool="shell", key="k2", status="error",
           error_class="timeout")
    record("tC", "outcome", tool="shell", key="k3", status="error",
           error_class="timeout")
    assert class_summary(read_thread("tC")) == {"ok": 1, "timeout": 2}


def test_show_missing_thread_errors(jhome):
    # read_thread on missing thread returns [] — CLI exit 1 path
    assert read_thread("nope") == []


def _run_cli(args, cwd):
    return subprocess.run(["uv", "run", "codemonkey", "journal"] + args,
                          capture_output=True, text=True, timeout=120, cwd=cwd)


def test_cli_list_and_show(jhome, monkeypatch):
    repo = "/Users/bharris/Programs/CodeMonkey"
    monkeypatch.chdir(repo)
    record("tCLI", "intent", tool="write_file", key="kx")
    record("tCLI", "outcome", tool="write_file", key="kx", status="ok",
           error_class="", duration_ms=5)

    r1 = _run_cli(["list"], repo)
    assert "tCLI" in r1.stdout

    r2 = _run_cli(["show", "tCLI"], repo)
    assert r2.returncode == 0
    assert "class summary" in r2.stdout
    assert "ok: 1" in r2.stdout

    r3 = _run_cli(["tail", "tCLI", "--last", "1"], repo)
    lines = [l for l in r3.stdout.splitlines() if l.startswith("{")]
    assert len(lines) == 1
    assert json.loads(lines[0])["key"] == "kx"
