"""Cycle 40 (loop11): delegation roles (CIV pattern)."""

from __future__ import annotations

import pytest

from codemonkey.sandbox import ToolContext
from codemonkey.tools.delegate import _ROLE_FRAMINGS, run


@pytest.fixture()
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


def test_unknown_role_rejected(ctx, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    res = run({"task": "x", "role": "boss"}, ctx)
    assert not res.ok
    assert "unknown role" in res.output


def test_all_three_roles_accepted(ctx, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("HOME", "/tmp")
    # stub the subprocess so no live model needed
    import subprocess as sp

    class P:
        returncode = 0
        stdout = "child-done"
        stderr = ""

    seen = {}
    real_run = sp.run

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return P()

    monkeypatch.setattr(sp, "run", fake_run)
    for role in ("implementer", "critic", "verifier"):
        res = run({"task": "do it", "role": role}, ctx)
        assert res.ok, res.output
        assert res.meta["role"] == role


def test_role_framing_in_child_task(ctx, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("HOME", "/tmp")
    import subprocess as sp

    class P:
        returncode = 0
        stdout = "ok"
        stderr = ""

    seen = {}
    def fake_run(cmd, **kw):
        seen["task"] = cmd[-1]
        return P()

    monkeypatch.setattr(sp, "run", fake_run)
    run({"task": "check the diff", "role": "critic"}, ctx)
    assert seen["task"].startswith("[critic role]")
    assert "VERDICT:" in seen["task"]
    assert "check the diff" in seen["task"]


def test_default_role_is_implementer(ctx, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_DELEGATE_DEPTH", raising=False)
    monkeypatch.setenv("HOME", "/tmp")
    import subprocess as sp

    seen = {}
    def fake_run(cmd, **kw):
        seen["task"] = cmd[-1]
        class P:
            returncode = 0; stdout = "ok"; stderr = ""
        return P()

    monkeypatch.setattr(sp, "run", fake_run)
    res = run({"task": "build it"}, ctx)
    assert seen["task"].startswith("[implementer role]")
    assert res.meta["role"] == "implementer"


def test_role_framings_content():
    assert "VERDICT" in _ROLE_FRAMINGS["critic"]
    assert "VERIFIED" in _ROLE_FRAMINGS["verifier"]
    assert "implementer" in _ROLE_FRAMINGS["implementer"] or "change" in _ROLE_FRAMINGS["implementer"]
