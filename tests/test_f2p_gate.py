"""Cycle 95 (loop 40): F2P quality gate + measurement.

Generated tests count as fix-evidence ONLY on an observed fail→pass;
pass-only is UNPROVEN. The ON-vs-OFF arms report pass rate, LOCAL F2P next
to the published 63% (R-G, never a chase), cost/wall (R-F), gate verdict.
"""

from __future__ import annotations

import json
import os

import pytest
import yaml

from codemonkey.f2p import (comparison_line, gate_verdict, label_task,
                            summarize_arm)
from codemonkey.matrix import render_f2p_table, run_f2p_matrix


# ---------------- unit: labels ----------------

def _v(verdict):
    return {"type": "repro.verdict", "report": {"verdict": verdict}}


def test_verified_labels_f2p():
    assert label_task([_v("VERIFIED")]) == "F2P"
    # last verdict wins
    assert label_task([_v("VERIFIED"), _v("UNVERIFIED")]) == "UNPROVEN"


def test_pass_only_labels_unproven():
    assert label_task([_v("UNVERIFIED")]) == "UNPROVEN"


def test_no_verdict_labels_na():
    assert label_task([{"type": "turn.completed"}]) == "N/A"
    assert label_task([]) == "N/A"


def test_summarize_arm_counts():
    run = {"pass_rate": 0.5, "total_tokens": 100, "wall_seconds": 4.0,
           "tasks": [{"f2p": "F2P"}, {"f2p": "UNPROVEN"}, {"f2p": "N/A"},
                     {"f2p": "F2P"}]}
    s = summarize_arm(run)
    assert s == {"pass_rate": 0.5, "tasks": 4, "labeled": 3, "f2p": 2,
                 "f2p_rate": 0.667, "total_tokens": 100, "wall_seconds": 4.0}


def test_gate_verdict_rules():
    thin = {"tasks": 2, "labeled": 1, "pass_rate": 1.0}
    v = gate_verdict(thin, thin)
    assert v["verdict"] == "INCONCLUSIVE"  # too thin for a reading
    v2 = gate_verdict({"tasks": 2, "labeled": 1, "pass_rate": 1.0},
                      {"tasks": 3, "labeled": 3, "pass_rate": 1.0})
    assert v2["verdict"] == "INCONCLUSIVE"  # mismatched arms
    v3 = gate_verdict({"tasks": 4, "labeled": 4, "pass_rate": 0.75},
                      {"tasks": 4, "labeled": 4, "pass_rate": 0.5})
    assert v3 == {"verdict": "MEASURED", "direction": "on-ahead",
                  "pass_rate_delta": 0.25,
                  "reason": "observational delta on one suite run; not causal"}


def test_comparison_line_states_frontier_not_target():
    line = comparison_line(0.25)
    assert "0.250" in line and "0.63" in line and "not a target" in line


# ---------------- matrix: two arms, fake exec ----------------

def _suite(tmp_path):
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.safe_dump({
        "name": "f2p",
        "tasks": [{"id": f"t{i}", "prompt": f"task {i}", "expect_exit": 0}
                  for i in range(4)],
    }))
    return p


def _fake_exec_factory():
    def fake_exec(prompt, **kw):
        events = kw.get("event_sink")
        # the OFF arm must see NO verdict: the loop only emits when the gate
        # is enabled, so the fake honors the same kill switch.
        if os.environ.get("CODEMONKEY_REPRO_GATE", "1") != "0":
            events.append({"type": "repro.verdict",
                           "report": {"verdict": "VERIFIED"}})
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "ok"}})
        events.append({"type": "turn.completed",
                       "usage": {"total_tokens": 10, "prompt_tokens": 100,
                                 "completion_tokens": 5}})
        return 0
    return fake_exec


def test_two_arms_and_labels(tmp_path):
    suite = _suite(tmp_path)
    results = run_f2p_matrix(suite, exec_fn=_fake_exec_factory(),
                             out_dir=tmp_path)
    assert set(results["arms"]) == {"repro-on", "repro-off"}
    on, off = results["arms"]["repro-on"], results["arms"]["repro-off"]
    assert on["pass_rate"] == 1.0 and off["pass_rate"] == 1.0
    assert on["labeled"] == 4 and on["f2p"] == 4 and on["f2p_rate"] == 1.0
    assert off["labeled"] == 0 and off["f2p_rate"] == 0.0
    assert "verdict" in results


def test_matrix_json_and_table(tmp_path):
    suite = _suite(tmp_path)
    results = run_f2p_matrix(suite, exec_fn=_fake_exec_factory(),
                             out_dir=tmp_path)
    data = json.loads((tmp_path / "f2p_matrix.json").read_text())
    assert set(data["arms"]) == {"repro-on", "repro-off"}
    table = render_f2p_table(results)
    assert "repro-on" in table and "repro-off" in table
    assert "0.63" in table and "gate verdict:" in table


def test_env_restored_after_matrix(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_REPRO_GATE", raising=False)
    run_f2p_matrix(_suite(tmp_path), exec_fn=_fake_exec_factory())
    assert "CODEMONKEY_REPRO_GATE" not in os.environ


def test_unknown_arm_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown f2p arm"):
        run_f2p_matrix(_suite(tmp_path), arms=["repro-on", "bogus"],
                       exec_fn=_fake_exec_factory())
