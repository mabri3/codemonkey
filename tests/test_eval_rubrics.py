"""Cycle 78 (loop 38): rubric steps compose into eval task scoring.

R-I entry-point probe: a golden-suite run where a task's stdout check passes
but its rubric fails → results.json shows the rubric verdict driving
ok=false; `codemonkey eval build/suites/rubric.yaml` prints per-task rubric
detail. Rubric-only tasks (no stdout contract) are allowed.
"""

from __future__ import annotations

import json

import yaml

from codemonkey.eval import _score_task, run_suite


def _task(**kw):
    base = {"id": "t", "prompt": "say hello"}
    base.update(kw)
    return base


# ---------------- composition ----------------

def test_stdout_pass_plus_rubric_pass_stays_ok():
    task = _task(expect_stdout_contains=["hello"],
                 rubric=["contains: hello", "absent: goodbye"])
    res = _score_task(task, exit_code=0, stdout="hello world",
                      events=[], wall=0.1)
    assert res["ok"] is True
    assert res["rubric"]["passed"] is True
    assert res["rubric"]["score"] == 1.0
    assert len(res["rubric"]["steps"]) == 2


def test_stdout_pass_plus_rubric_fail_drives_ok_false():
    """The core: stdout contract green, rubric red → task fails."""
    task = _task(expect_stdout_contains=["hello"],
                 rubric=["contains: hello", "contains: goodbye"])
    res = _score_task(task, exit_code=0, stdout="hello world",
                      events=[], wall=0.1)
    assert res["checks"]["stdout"] is True  # stdout check itself passed
    assert res["rubric"]["passed"] is False
    assert res["rubric"]["score"] == 0.5
    assert res["ok"] is False


def test_rubric_only_task_no_stdout_contract():
    task = _task(rubric=["regex: ^hello", "absent: banana"])
    ok_res = _score_task(task, exit_code=0, stdout="hello there",
                         events=[], wall=0.1)
    assert ok_res["ok"] is True
    bad_res = _score_task(task, exit_code=0, stdout="hello banana",
                          events=[], wall=0.1)
    assert bad_res["ok"] is False
    assert bad_res["rubric"]["passed"] is False


def test_no_rubric_leaves_no_rubric_key():
    task = _task(expect_stdout_contains=["hello"])
    res = _score_task(task, exit_code=0, stdout="hello",
                      events=[], wall=0.1)
    assert res["ok"] is True
    assert "rubric" not in res


# ---------------- R-I: golden-suite run ----------------

def _write_suite(tmp_path, data):
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump(data))
    return p


def test_suite_run_records_rubric_verdict(tmp_path):
    """results.json shows the rubric verdict driving ok=false."""
    suite_path = _write_suite(tmp_path, {
        "name": "rubric-probe",
        "tasks": [
            {"id": "clean", "prompt": "say hello",
             "expect_stdout_contains": ["hello"],
             "rubric": ["contains: hello"]},
            {"id": "rubfail", "prompt": "say hello",
             "expect_stdout_contains": ["hello"],
             "rubric": ["contains: goodbye"]},
        ],
    })

    def fake_exec(prompt, **kwargs):
        events = kwargs.get("event_sink")
        assert events is not None
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "hello"}})
        return 0

    results = run_suite(suite_path, exec_fn=fake_exec,
                        out_dir=tmp_path / "eval")
    by_id = {t["id"]: t for t in results["tasks"]}
    assert by_id["clean"]["ok"] is True
    assert by_id["rubfail"]["checks"]["stdout"] is True
    assert by_id["rubfail"]["rubric"]["passed"] is False
    assert by_id["rubfail"]["ok"] is False
    data = json.loads((tmp_path / "eval" / "results.json").read_text())
    assert data["tasks"][1]["rubric"]["passed"] is False
