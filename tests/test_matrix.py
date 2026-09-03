"""Cycle 28 (loop6): compaction strategy bake-off.

Verify probe (plan.md): >=5 tests — matrix runs both configs via patched exec,
depth recorded per turn, matrix.json shape, comparison table prints, tie
handling.
"""

from __future__ import annotations

import json

import pytest
import yaml

from codemonkey.matrix import render_table, run_matrix
from codemonkey.eval import run_suite


class Turn:
    def __init__(self, content, prompt_tokens):
        self.content = content
        self.usage = {"total_tokens": 10, "prompt_tokens": prompt_tokens,
                      "completion_tokens": 2}
        self.tool_calls = []


def _write_suite(tmp_path, n_tasks=2):
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump({
        "name": "matrix-suite",
        "tasks": [{"id": f"t{i}", "prompt": f"task {i}",
                   "expect_exit": 0} for i in range(n_tasks)],
    }))
    return p


def test_matrix_runs_both_configs(tmp_path):
    suite = _write_suite(tmp_path)
    seen_strategies = []

    def fake_exec(prompt, **kw):
        import os
        seen_strategies.append(os.environ.get("CODEMONKEY_STRATEGY_COMPACTION"))
        events = kw.get("event_sink")
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "ok"}})
        events.append({"type": "turn.completed",
                       "usage": {"total_tokens": 10, "prompt_tokens": 500,
                                 "completion_tokens": 2}})
        return 0

    results = run_matrix(suite, ["summarizing", "sliding-window"],
                         exec_fn=fake_exec, out_dir=tmp_path)
    # one run per strategy (2 tasks each), env set per run
    assert seen_strategies == ["summarizing", "summarizing",
                               "sliding-window", "sliding-window"]
    assert set(results["strategies"]) == {"summarizing", "sliding-window"}
    # env restored
    import os
    assert "CODEMONKEY_STRATEGY_COMPACTION" not in os.environ or \
        os.environ["CODEMONKEY_STRATEGY_COMPACTION"] == "summarizing"


def test_window_depth_recorded(tmp_path):
    suite = _write_suite(tmp_path, n_tasks=1)

    def fake_exec(prompt, **kw):
        events = kw.get("event_sink")
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "ok"}})
        events.append({"type": "turn.completed",
                       "usage": {"total_tokens": 10, "prompt_tokens": 1234,
                                 "completion_tokens": 2}})
        events.append({"type": "turn.completed",
                       "usage": {"total_tokens": 10, "prompt_tokens": 2345,
                                 "completion_tokens": 2}})
        return 0

    results = run_matrix(suite, ["summarizing"], exec_fn=fake_exec)
    # depth = MAX prompt_tokens across turns
    assert results["strategies"]["summarizing"]["window_depth"] == 2345


def test_matrix_json_shape(tmp_path):
    suite = _write_suite(tmp_path)
    results = run_matrix(suite, ["summarizing", "sliding-window"],
                         exec_fn=lambda p, **kw: (kw.get("event_sink").append(
                             {"type": "item.completed",
                              "item": {"type": "agent_message", "text": "ok"}}), 0)[1],
                         out_dir=tmp_path)
    data = json.loads((tmp_path / "matrix.json").read_text())
    for strat in ("summarizing", "sliding-window"):
        d = data["strategies"][strat]
        assert {"pass_rate", "total_tokens", "wall_seconds", "window_depth",
                "tasks"} <= set(d)
        assert d["tasks"]["t0"]["ok"] is True


def test_table_prints_aligned(tmp_path):
    suite = _write_suite(tmp_path)
    results = run_matrix(suite, ["summarizing", "sliding-window"],
                         exec_fn=lambda p, **kw: (kw.get("event_sink").append(
                             {"type": "item.completed",
                              "item": {"type": "agent_message", "text": "ok"}}), 0)[1])
    table = render_table(results)
    lines = table.splitlines()
    assert lines[0].split() == ["strategy", "pass_rate", "tokens", "wall_s", "depth"]
    assert "summarizing" in table and "sliding-window" in table
    # columns aligned: all data rows same width
    assert len({len(ln) for ln in lines[2:]}) == 1


def test_single_strategy_and_ties(tmp_path):
    suite = _write_suite(tmp_path)

    def fake_exec(prompt, **kw):
        events = kw.get("event_sink")
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "ok"}})
        return 0

    results = run_matrix(suite, ["summarizing"], exec_fn=fake_exec)
    assert render_table(results).count("\n") == 2  # header + rule + 1 row
    # tie: same pass_rate for both strategies renders without error
    results2 = run_matrix(suite, ["summarizing", "sliding-window"],
                          exec_fn=fake_exec)
    assert results2["strategies"]["summarizing"]["pass_rate"] == \
        results2["strategies"]["sliding-window"]["pass_rate"] == 1.0
