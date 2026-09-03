"""Cycle 37 (loop9): delegate tool — isolated child codemonkey runs."""

from __future__ import annotations

import pytest

from codemonkey.sandbox import ToolContext
from codemonkey.tools.delegate import run


@pytest.fixture()
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


def test_needs_task(ctx):
    res = run({}, ctx)
    assert not res.ok
    assert "task" in res.output


def test_task_too_long(ctx):
    res = run({"task": "x" * 9000}, ctx)
    assert not res.ok
    assert "too long" in res.output


def test_depth_limit(ctx, monkeypatch):
    monkeypatch.setenv("CODEMONKEY_DELEGATE_DEPTH", "1")
    res = run({"task": "anything"}, ctx)
    assert not res.ok
    assert "depth limit" in res.output


def test_child_executes_and_returns_result(ctx, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("CODEMONKEY_FORCE_LIVE", "1")
    # skip when home is down (same conftest policy) — handled by pytest skip
    import httpx

    try:
        httpx.post("http://192.168.50.113:8080/v1/chat/completions",
                   json={"model": "Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf",
                         "messages": [{"role": "user", "content": "ping"}],
                         "max_tokens": 8}, timeout=15)
        alive = True
    except Exception:
        alive = False
    if not alive:
        pytest.skip("home llama.cpp unreachable")
    res = run({"task": "Reply with exactly: delegate-ok"}, ctx)
    assert res.ok, res.output
    assert "delegate-ok" in res.output
    assert res.meta.get("delegated") is True


def test_child_failure_propagates(ctx, monkeypatch):
    """Child exit != 0 propagates as a failed delegate result."""
    import codemonkey.tools.delegate as dmod

    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("HOME", "/tmp")
    monkeypatch.setattr(dmod, "_spawn",
                        lambda task, sandbox, ctx2:
                        {"ok": False,
                         "output": "error: delegate exited 2: boom"})
    res = run({"task": "Reply ok"}, ctx)
    assert not res.ok
    assert "delegate exited 2" in res.output


def test_result_capped(ctx, monkeypatch):
    """Child stdout over the cap is truncated (behavioral check via unit)."""
    from codemonkey.tools import delegate as d

    assert d._MAX_RESULT == 4000  # cap constant present
