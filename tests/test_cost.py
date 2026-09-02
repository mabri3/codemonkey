"""Cycle 26 (loop5): token/cost telemetry.

Verify probe (plan.md): >=4 tests — run totals in JSONL summary, ledger append,
cumulative across runs, --cost-summary output shape.
"""

from __future__ import annotations

import json

import pytest

from codemonkey.cost import append_to_ledger, render_summary, summarize


def _events():
    return [
        {"type": "thread.started", "thread_id": "t"},
        {"type": "turn.started"},
        {"type": "turn.completed", "usage": {"total_tokens": 100, "prompt_tokens": 80, "completion_tokens": 20}},
        {"type": "tool.started", "name": "shell"},
        {"type": "tool.completed", "name": "shell", "ok": True},
        {"type": "tool.started", "name": "shell"},
        {"type": "tool.started", "name": "read_file"},
        {"type": "turn.started"},
        {"type": "turn.completed", "usage": {"total_tokens": 50, "prompt_tokens": 40, "completion_tokens": 10}},
    ]


def test_summarize_totals():
    s = summarize(_events(), wall_seconds=1.5)
    assert s["turns"] == 2
    assert s["total_tokens"] == 150
    assert s["prompt_tokens"] == 120
    assert s["completion_tokens"] == 30
    assert s["tool_calls"] == {"shell": 2, "read_file": 1}
    assert s["wall_seconds"] == 1.5


def test_ledger_append_and_cumulative(tmp_path):
    p = tmp_path / "cost.json"
    s1 = summarize(_events())
    led = append_to_ledger(s1, path=p)
    assert led["total_tokens"] == 150
    s2 = summarize(_events())
    led = append_to_ledger(s2, path=p)
    assert led["total_tokens"] == 300  # cumulative across runs
    assert len(led["runs"]) == 2
    on_disk = json.loads(p.read_text())
    assert on_disk["total_tokens"] == 300


def test_render_summary_shape():
    s = summarize(_events(), wall_seconds=2.0)
    text = render_summary(s)
    assert "turns: 2" in text
    assert "tokens: 150" in text
    assert "prompt 120" in text
    assert "wall: 2.0s" in text
    assert "shell x2" in text


def test_render_summary_no_tools():
    text = render_summary({"turns": 1, "total_tokens": 5, "prompt_tokens": 4,
                           "completion_tokens": 1, "tool_calls": {}, "wall_seconds": 0.5})
    assert "tool calls: none" in text


def test_exec_cost_summary_flag(tmp_path, monkeypatch):
    """--cost-summary end-to-end: exec prints summary + ledger written."""
    import codemonkey.loop as loop_mod
    import subprocess

    repo = "/Users/bharris/Programs/CodeMonkey"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("CODEMONKEY_COST_LEDGER", str(tmp_path / "cost.json"))

    r = subprocess.run(
        ["uv", "run", "codemonkey", "exec", "--ephemeral", "--cost-summary",
         "Reply with exactly: cost-ok"],
        capture_output=True, text=True, timeout=300, cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tokens:" in r.stderr
    assert "turns:" in r.stderr
