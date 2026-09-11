"""loop46 cycle 87 — the R-K measurement plumbing (skills arms).

Three properties are load-bearing and each gets a discriminating test:

* With a scripted exec function and an answering endpoint, the arms produce
  real numbers and a delta — the plumbing RUNS.
* With no endpoint, the figures are BLOCKED-with-reason and `None` — never 0.
* The contamination check catches the case the whole claim rests on: a skill
  that was created during the measurement (either a new store entry, or an
  entry bearing a created-time that postdates the start).
"""

from __future__ import annotations

import json
from pathlib import Path

from codemonkey import skills
from codemonkey import skills_arms


SUITE = """name: arm-suite
tasks:
  - id: t1
    prompt: "task one"
  - id: t2
    prompt: "task two"
"""


def _suite(tmp: Path, name="suite.yaml") -> Path:
    p = tmp / name
    p.write_text(SUITE)
    return p


def _exec_ok(prompt, **kw):
    sink = kw.get("event_sink")
    if sink is not None:
        sink.append({"type": "item.completed",
                     "item": {"type": "agent_message", "text": "ok"}})
    return 0


def _exec_transport(prompt, **kw):
    return 1  # every task fails; the probe below is what says WHY


def test_arms_produce_measured_delta_with_a_scripted_exec(tmp_path):
    res = skills_arms.run_skills_matrix(
        _suite(tmp_path), exec_fn=_exec_ok, probe=lambda: "")
    assert res["verdict"] == "MEASURED"
    assert res["arms"]["skills-on"]["pass_rate"] == 1.0
    assert res["arms"]["skills-off"]["pass_rate"] == 1.0
    assert res["forward_transfer"]["value"] == 0.0
    assert res["contamination"]["violations"] == []
    assert "hoeffding-gate" in res["statistic"]


def test_no_endpoint_is_blocked_with_none_never_zero(tmp_path):
    res = skills_arms.run_skills_matrix(
        _suite(tmp_path), exec_fn=_exec_transport,
        probe=lambda: "ConnectError: [Errno 61] Connection refused")
    assert res["verdict"] == "BLOCKED"
    assert res["forward_transfer"]["value"] is None      # None — never 0
    assert "Connection refused" in res["forward_transfer"]["reason"]
    assert res["retention_check"]["value"] is None
    text = skills_arms.render_skills_table(res)
    assert "BLOCKED" in text and "never 0" in text


def test_contamination_catches_a_skill_created_during_measurement(tmp_path):
    def _exec_that_learns(prompt, **kw):
        skills.write_manifest(tmp_path, {
            "name": "sneaky", "spec": "made mid-measurement",
            "params": {"type": "object", "properties": {}},
            "probe": "true",
            "provenance": {"run_id": "r-mid", "session_id": "s-mid",
                           "taint_free": True},
            "status": "quarantined"})
        return 0

    res = skills_arms.run_skills_matrix(
        _suite(tmp_path), exec_fn=_exec_that_learns, probe=lambda: "",
        store=tmp_path)
    assert res["verdict"] == "CONTAMINATED"
    joined = " ".join(res["contamination"]["violations"])
    assert "sneaky" in joined


def test_contamination_catches_a_backdated_store_entry(tmp_path):
    """The snapshot-diff cannot see a PRE-EXISTING entry whose created time
    postdates the start — the timestamp rule must."""
    d = tmp_path / skills.STORE_DIR / "future_skill"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({
        "name": "future_skill", "spec": "created in the future",
        "params": {"type": "object", "properties": {}},
        "probe": "true",
        "provenance": {"run_id": "r1", "session_id": "s1",
                       "taint_free": True},
        "status": "admitted",
        "created": "2099-01-01T00:00:00Z"}))
    res = skills_arms.run_skills_matrix(
        _suite(tmp_path), exec_fn=_exec_ok, probe=lambda: "",
        store=tmp_path)
    assert res["verdict"] == "CONTAMINATED"
    assert any("not before the measurement start" in v
               for v in res["contamination"]["violations"])


def test_retention_runs_on_the_earlier_suite(tmp_path):
    earlier = _suite(tmp_path, "earlier.yaml")
    res = skills_arms.run_skills_matrix(
        _suite(tmp_path), exec_fn=_exec_ok, probe=lambda: "",
        retention_suite=earlier)
    assert res["retention_check"]["status"] == "MEASURED"
    assert res["retention_check"]["value"] == 0.0
    assert res["retention"]["skills-on"]["tasks"] == 2


def test_unknown_arm_is_refused(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        skills_arms.run_skills_matrix(
            _suite(tmp_path), exec_fn=_exec_ok, probe=lambda: "",
            arms=["skills-on", "bogus"])
