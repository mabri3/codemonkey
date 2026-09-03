"""Cycle 42 (loop11): delegation ROI matrix."""

from __future__ import annotations

import json

import pytest
import yaml

from codemonkey.matrix import render_table, run_delegation_matrix


def _suite(tmp_path):
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump({
        "name": "deleg",
        "tasks": [{"id": f"t{i}", "prompt": f"task {i}", "expect_exit": 0}
                  for i in range(2)],
    }))
    return p


def _fake_exec_factory(delay_first=False):
    def fake_exec(prompt, **kw):
        events = kw.get("event_sink")
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "ok"}})
        events.append({"type": "turn.completed",
                       "usage": {"total_tokens": 10, "prompt_tokens": 100,
                                 "completion_tokens": 5}})
        return 0
    return fake_exec


def test_two_arms_run(tmp_path):
    suite = _suite(tmp_path)
    results = run_delegation_matrix(suite, exec_fn=_fake_exec_factory(),
                                    out_dir=tmp_path)
    assert set(results["arms"]) == {"no-delegation", "delegation"}
    assert results["arms"]["no-delegation"]["pass_rate"] == 1.0


def test_matrix_json_shape(tmp_path):
    suite = _suite(tmp_path)
    run_delegation_matrix(suite, exec_fn=_fake_exec_factory(), out_dir=tmp_path)
    data = json.loads((tmp_path / "delegation_matrix.json").read_text())
    for arm in ("no-delegation", "delegation"):
        d = data["arms"][arm]
        assert {"pass_rate", "total_tokens", "wall_seconds", "window_depth"} <= set(d)


def test_table_renders(tmp_path):
    suite = _suite(tmp_path)
    results = run_delegation_matrix(suite, exec_fn=_fake_exec_factory())
    table = render_table({"strategies": results["arms"]})
    assert "no-delegation" in table and "delegation" in table


def test_custom_arms(tmp_path):
    suite = _suite(tmp_path)
    results = run_delegation_matrix(
        suite, exec_fn=_fake_exec_factory(),
        arms=[("plain", None), ("impl", {"role": "implementer"}),
              ("critic", {"role": "critic"})])
    assert set(results["arms"]) == {"plain", "impl", "critic"}
