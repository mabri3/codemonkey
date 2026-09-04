"""Cycle 24 (loop5): eval harness core.

Verify probe (plan.md): >=5 tests — YAML load (+malformed rejection), task run
via patched exec, stdout-contract scoring, trajectory scoring, results.json
shape. Plus a LIVE 2-task suite against the home server.
"""

from __future__ import annotations

import json

import pytest
import yaml

from codemonkey.eval import _score_task, _trajectory_from_events, load_suite, run_suite


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


def _write_suite(tmp_path, data):
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


# ---------------- suite loading ----------------

def test_load_suite_valid(tmp_path):
    p = _write_suite(tmp_path, {
        "name": "s1",
        "tasks": [{"id": "t1", "prompt": "hello", "expect_exit": 0}],
    })
    suite = load_suite(p)
    assert suite["name"] == "s1"
    assert suite["tasks"][0]["id"] == "t1"


def test_load_suite_rejects_malformed(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("not: a\nsuite: [")
    with pytest.raises(ValueError):
        load_suite(p)
    p2 = tmp_path / "empty.yaml"
    p2.write_text("name: x\n")
    with pytest.raises(ValueError):
        load_suite(p2)


# ---------------- trajectory extraction ----------------

def test_trajectory_from_events_order_dedup():
    events = [
        {"type": "tool.started", "name": "shell"},
        {"type": "tool.started", "name": "read_file"},
        {"type": "tool.started", "name": "shell"},  # repeat ignored
        {"type": "tool.started", "name": "write_file"},
    ]
    assert _trajectory_from_events(events) == ["shell", "read_file", "write_file"]


# ---------------- scoring ----------------

def test_stdout_contract_scoring():
    task = {"id": "t", "prompt": "p", "expect_stdout_contains": ["pong"],
            "expect_stdout_not_contains": ["banana"]}
    ok = _score_task(task, exit_code=0, stdout="pong!", events=[], wall=0.1)
    assert ok["ok"] and ok["checks"]["stdout"]
    bad = _score_task(task, exit_code=0, stdout="banana", events=[], wall=0.1)
    assert not bad["ok"]
    assert "pong" in bad["detail"]["missing_stdout"]
    assert "banana" in bad["detail"]["forbidden_stdout_found"]


def test_trajectory_scoring_subset_in_order():
    task = {"id": "t", "prompt": "p", "expect_tools": ["shell", "write_file"]}
    events = [
        {"type": "tool.started", "name": "read_file"},   # extra tool fine
        {"type": "tool.started", "name": "shell"},
        {"type": "tool.started", "name": "shell"},       # dup
        {"type": "tool.started", "name": "write_file"},
    ]
    ok = _score_task(task, exit_code=0, stdout="x", events=events, wall=0.1)
    assert ok["checks"]["trajectory"]
    wrong_order = [
        {"type": "tool.started", "name": "write_file"},
        {"type": "tool.started", "name": "shell"},
    ]
    bad = _score_task(task, exit_code=0, stdout="x", events=wrong_order, wall=0.1)
    assert not bad["checks"]["trajectory"]


# ---------------- end-to-end with patched exec ----------------

def test_run_suite_with_fake_exec(tmp_path):
    suite_path = _write_suite(tmp_path, {
        "name": "fake-suite",
        "tasks": [
            {"id": "pass", "prompt": "say pong",
             "expect_stdout_contains": ["pong"], "expect_exit": 0},
            {"id": "fail", "prompt": "say banana",
             "expect_stdout_contains": ["pong"], "expect_exit": 0},
        ],
    })

    def fake_exec(prompt, **kwargs):
        events = kwargs.get("event_sink")
        if "pong" in prompt:
            events.append({"type": "item.completed", "item": {"type": "agent_message", "text": "pong"}})
            events.append({"type": "turn.completed", "usage": {"total_tokens": 42}})
            return 0
        events.append({"type": "item.completed", "item": {"type": "agent_message", "text": "banana"}})
        events.append({"type": "turn.completed", "usage": {"total_tokens": 7}})
        return 0

    results = run_suite(suite_path, exec_fn=fake_exec, out_dir=tmp_path / "eval")
    assert results["pass_rate"] == 0.5
    assert results["total_tokens"] == 49
    by_id = {t["id"]: t for t in results["tasks"]}
    assert by_id["pass"]["ok"] and not by_id["fail"]["ok"]
    # results.json written and parses
    data = json.loads((tmp_path / "eval" / "results.json").read_text())
    assert data["suite"] == "fake-suite"
    assert len(data["tasks"]) == 2


# ---------------- early-stop gate (loop38, cycle 77, R-H) ----------------

def _all_pass_fake(prompt, **kwargs):
    events = kwargs.get("event_sink")
    events.append({"type": "item.completed",
                   "item": {"type": "agent_message", "text": "pong"}})
    events.append({"type": "turn.completed", "usage": {"total_tokens": 1}})
    return 0


def _six_task_suite(tmp_path):
    return _write_suite(tmp_path, {
        "name": "trivial",
        "tasks": [
            {"id": f"t{i}", "prompt": "say pong",
             "expect_stdout_contains": ["pong"], "expect_exit": 0}
            for i in range(1, 7)
        ],
    })


def test_early_stop_settles_before_task_6(tmp_path):
    """R-I (offline arm): 6 all-pass tasks, delta 0.2 → gate settles at n=4,
    tasks 5-6 never run, certificate names the hoeffding-gate."""
    suite_path = _six_task_suite(tmp_path)
    calls = []

    def counting_fake(prompt, **kwargs):
        calls.append(prompt)
        return _all_pass_fake(prompt, **kwargs)

    results = run_suite(suite_path, exec_fn=counting_fake,
                        out_dir=tmp_path / "eval",
                        early_stop=True, delta=0.2)
    assert len(calls) == 4  # stopped before task 6 (tasks 5, 6 skipped)
    assert len(results["tasks"]) == 4
    assert results["stopped_early"] is True
    cert = results["certificate"]
    assert cert["kind"] == "hoeffding-gate"
    assert cert["certified_pass"] is True
    assert cert["at_n"] == 4


def test_no_early_stop_runs_everything(tmp_path):
    suite_path = _six_task_suite(tmp_path)
    results = run_suite(suite_path, exec_fn=_all_pass_fake,
                        out_dir=tmp_path / "eval")
    assert len(results["tasks"]) == 6
    assert results["stopped_early"] is False
    assert "certificate" not in results


def test_early_stop_undecided_runs_everything(tmp_path):
    suite_path = _write_suite(tmp_path, {
        "name": "tied",
        "tasks": [
            {"id": f"t{i}", "prompt": "say pong",
             "expect_stdout_contains": ["pong"] if i % 2 else ["nope"],
             "expect_exit": 0}
            for i in range(6)
        ],
    })
    results = run_suite(suite_path, exec_fn=_all_pass_fake,
                        out_dir=tmp_path / "eval",
                        early_stop=True, delta=0.2)
    assert len(results["tasks"]) == 6  # never settles: full run
    assert results["stopped_early"] is False
