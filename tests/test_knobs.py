"""Cycle 17F1: loop-3 knobs as real config knobs.

Verify probe (plan.md): >=3 tests — defaults present in config; env override
applied; exec passes both values through to run_turns (patched run_turns
recording kwargs).
"""

from __future__ import annotations

import pytest


def test_defaults_present():
    from codemonkey.config import DEFAULTS

    assert DEFAULTS["max_edit_retries"] == 1
    assert DEFAULTS["observation_budget"] == 24000


def test_env_override_applied(monkeypatch):
    from codemonkey.config import load_config

    monkeypatch.setenv("CODEMONKEY_OBSERVATION_BUDGET", "5000")
    monkeypatch.setenv("CODEMONKEY_MAX_EDIT_RETRIES", "3")
    cfg = load_config(ignore_user_config=True)
    assert cfg["observation_budget"] == 5000
    assert cfg["max_edit_retries"] == 3


def test_exec_passes_knobs_to_run_turns(tmp_path, monkeypatch):
    """Patch run_turns inside exec's module and record its kwargs."""
    import codemonkey.exec as exec_mod
    import codemonkey.loop as loop_mod

    recorded = {}

    def fake_run_turns(provider, user_prompt, ctx, **kwargs):
        recorded.update(kwargs)
        turn = type("T", (), {})()
        turn.content = "ok"
        turn.reasoning = None
        turn.usage = {"total_tokens": 1}
        turn.all_messages = list(kwargs.get("history") or []) + [
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": "ok"},
        ]
        return turn

    monkeypatch.setattr(loop_mod, "run_turns", fake_run_turns)
    monkeypatch.setenv("CODEMONKEY_PROVIDER", "unblock2")
    monkeypatch.setenv("CODEMONKEY_UNBLOCK2_KEY", "test-key")
    monkeypatch.setenv("CODEMONKEY_MAX_EDIT_RETRIES", "4")
    monkeypatch.setenv("CODEMONKEY_OBSERVATION_BUDGET", "12345")

    exec_mod.run_exec("say ok", provider_name="unblock2", ephemeral=True, stdin_cm="")

    assert recorded.get("max_edit_retries") == 4
    assert recorded.get("observation_budget") == 12345


def test_config_command_prints_knobs():
    import subprocess

    r = subprocess.run(
        ["uv", "run", "codemonkey", "config"],
        capture_output=True, text=True, timeout=120,
        cwd="/Users/bharris/Programs/CodeMonkey",
    )
    assert r.returncode == 0
    assert "max_edit_retries" in r.stdout
    assert "observation_budget" in r.stdout
