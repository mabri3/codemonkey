"""Cycle 46 (loop13): verified-by-eval gate for lessons."""

from __future__ import annotations

import json

import pytest

from codemonkey.lessons import add, load_all
from codemonkey.lessons_gate import gate_lesson_with_eval, injection_entries


@pytest.fixture()
def lhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_flip_verified_on_green_eval(lhome, tmp_path):
    e = add("lesson about timeouts", tool="shell", error_class="timeout",
            verified=False)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"pass_rate": 1.0, "tasks": {}}))
    results = {"pass_rate": 1.0, "tasks": [{"id": "t", "ok": True}]}
    out = gate_lesson_with_eval(e["id"], results, baseline)
    assert out["verified"] is True
    assert load_all()[0]["verified"] is True


def test_revert_on_baseline_regression(lhome, tmp_path):
    e = add("lesson", tool="shell", error_class="timeout", verified=True)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"pass_rate": 1.0,
                                    "tasks": {"t": {"ok": True}}}))
    results = {"pass_rate": 0.0, "tasks": [{"id": "t", "ok": False}]}
    out = gate_lesson_with_eval(e["id"], results, baseline)
    assert out["verified"] is False  # regression reverts adoption
    assert load_all()[0]["verified"] is False


def test_no_baseline_adopts_only_perfect_run(lhome, tmp_path):
    e = add("lesson", tool="shell", error_class="timeout", verified=False)
    imperfect = {"pass_rate": 0.5, "tasks": []}
    out = gate_lesson_with_eval(e["id"], imperfect, tmp_path / "none.json")
    assert out["verified"] is False
    perfect = {"pass_rate": 1.0, "tasks": []}
    out = gate_lesson_with_eval(e["id"], perfect, tmp_path / "none.json")
    assert out["verified"] is True


def test_injection_excludes_unverified(lhome):
    add("verified lesson about shell timeouts", tool="shell",
        error_class="timeout", verified=True)
    add("unverified draft lesson", tool="shell", error_class="timeout",
        verified=False)
    hits = injection_entries("shell timeout problems again")
    assert len(hits) == 1
    assert hits[0]["text"].startswith("verified")


def test_gate_result_persists(lhome, tmp_path):
    e = add("lesson", tool="shell", error_class="timeout", verified=False)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps({"pass_rate": 1.0, "tasks": {}}))
    results = {"pass_rate": 1.0, "tasks": []}
    gate_lesson_with_eval(e["id"], results, baseline)
    # a second gate with no regression keeps it verified
    out = gate_lesson_with_eval(e["id"], results, baseline)
    assert out["verified"] is True
