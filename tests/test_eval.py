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
