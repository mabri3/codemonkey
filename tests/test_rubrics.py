"""R33: rubrics + step-level scoring."""

from __future__ import annotations

from codemonkey.rubrics import rubric_from_yaml_steps, score_rubric


RUBRIC = [
    {"id": "greeting", "kind": "contains", "value": "hello"},
    {"id": "num", "kind": "regex", "value": r"\d+"},
    {"id": "clean", "kind": "absent", "value": "sorry"},
]


def test_all_steps_pass():
    res = score_rubric("hello! pick 42 right away", RUBRIC)
    assert res["passed"] and res["score"] == 1.0


def test_partial_score_and_fail():
    res = score_rubric("hello world", RUBRIC)
    assert not res["passed"] and res["score"] == round(2 / 3, 3)
    assert [s["ok"] for s in res["steps"]] == [True, False, True]


def test_absent_semantics():
    res = score_rubric("so sorry", [{"id": "x", "kind": "absent", "value": "sorry"}])
    assert res["steps"][0]["ok"] is False


def test_yaml_sugar():
    steps = rubric_from_yaml_steps(["contains: hello", "regex: \\d+"])
    assert steps[0] == {"id": "step1", "kind": "contains", "value": "hello"}
    res = score_rubric("hello 7", steps)
    assert res["passed"]


def test_empty_rubric():
    res = score_rubric("anything", [])
    assert res["passed"] is False or res["steps"] == []
