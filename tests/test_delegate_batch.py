"""Cycle 38 (loop9): parallel fan-out (delegate_batch)."""

from __future__ import annotations

import pytest

from codemonkey.sandbox import ToolContext
from codemonkey.tools.delegate_batch import run


@pytest.fixture()
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


def test_needs_tasks(ctx):
    res = run({}, ctx)
    assert not res.ok
    assert "tasks" in res.output


def test_empty_batch(ctx):
    res = run({"tasks": []}, ctx)
    assert not res.ok


def test_too_many_tasks(ctx):
    res = run({"tasks": [{"task": f"t{i}"} for i in range(10)]}, ctx)
    assert not res.ok
    assert "too many" in res.output


def test_depth_limit(ctx, monkeypatch):
    monkeypatch.setenv("CODEMONKEY_DELEGATE_DEPTH", "1")
    res = run({"tasks": [{"task": "x"}]}, ctx)
    assert not res.ok
    assert "depth limit" in res.output


def test_aggregation_in_call_order(ctx, monkeypatch):
    """Results aggregated by index even though workers finish out of order —
    verified with stubbed delegate runs (no live model needed)."""
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("HOME", "/tmp")  # isolate journal
    from codemonkey.tools import delegate_batch as db

    calls = {"n": 0}

    class FakeRes:
        def __init__(self, ok, output):
            self.ok = ok
            self.output = output

    def fake_delegate(task_args, ctx2):
        calls["n"] += 1
        # finish out of order: first task sleeps
        import time

        if calls["n"] == 1:
            time.sleep(0.3)
        task = task_args.get("task", "")
        return FakeRes(True, f"result-for[{task}]")

    import codemonkey.tools.delegate as dmod

    monkeypatch.setattr(dmod, "run", fake_delegate)
    res = run({"tasks": ["alpha", "beta", "gamma"]}, ctx)
    assert res.ok
    a = res.output.find("[ok] task 0: result-for[alpha]")
    b = res.output.find("[ok] task 1: result-for[beta]")
    c = res.output.find("[ok] task 2: result-for[gamma]")
    assert 0 <= a < b < c


def test_per_task_isolation(ctx, monkeypatch):
    """One failing task does not kill siblings."""
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("HOME", "/tmp")
    from codemonkey.tools import delegate_batch as db

    class FakeRes:
        def __init__(self, ok, output):
            self.ok = ok
            self.output = output

    def fake_delegate(task_args, ctx2):
        task = task_args.get("task", "")
        if task == "boom":
            return FakeRes(False, "error: child failed")
        return FakeRes(True, f"result-for[{task}]")

    import codemonkey.tools.delegate as dmod

    monkeypatch.setattr(dmod, "run", fake_delegate)
    res = run({"tasks": ["alpha", "boom", "gamma"]}, ctx)
    assert not res.ok  # one failure -> batch not fully ok
    assert "result-for[alpha]" in res.output
    assert "result-for[gamma]" in res.output
    assert "[FAIL] task 1" in res.output
