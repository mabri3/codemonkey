"""loop50 cycle 122 — the long-horizon suite + Fix Rate.

Claims pinned:

* the real suite file (`build/suites/long-horizon.yaml`) runs to completion
  through the real `run_suite` harness (scripted exec standing in for the
  model): all three tasks pass in order through the state the previous task
  wrote;
* the ORDER-DEPENDENCE control: `lh2` run FIRST in a fresh workspace FAILS
  its precondition (the missing "ALPHA-BUILD" needle lands in `detail`) —
  the suite's order-dependence is a property of the suite, proven by the
  run that violates it;
* Fix Rate: a 2-of-3-check fixture reads `fix_rate 0.667, pass_rate 0`;
  a fully passing task reads `1.0` and the suite aggregates over DECLARED
  checks, not tasks (an empty suite is `None`, never 0).
"""

from __future__ import annotations

from pathlib import Path

from codemonkey import eval as eval_mod


SUITE = Path(__file__).resolve().parents[1] / "build" / "suites" / "long-horizon.yaml"


class ScriptedState:
    """Stands in for the model: honors the order-dependence semantics of the
    suite by reading/writing the state the prompts describe."""

    def __init__(self, workdir: Path):
        self.wd = workdir
        self.calls: list[str] = []

    def __call__(self, prompt, **kw):
        self.calls.append(prompt)
        state1 = self.wd / "state" / "step1.txt"
        msg = ""
        if "step 1" in prompt:
            state1.parent.mkdir(parents=True, exist_ok=True)
            state1.write_text("ALPHA-BUILD")
            msg = "step-one done (ALPHA-BUILD)"
        elif "step 2" in prompt:
            if state1.exists() and "ALPHA-BUILD" in state1.read_text():
                msg = "step-two got ALPHA-BUILD"
            else:
                msg = "step-two got nothing (no artifact)"
        elif "step 3" in prompt:
            if state1.exists():
                (self.wd / "state" / "step3.txt").write_text(
                    state1.read_text() + "-FINAL")
                msg = "step-three wrote ALPHA-BUILD-FINAL"
            else:
                msg = "step-three wrote nothing"
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": msg}})
        return 0


def test_suite_runs_in_order_and_fix_rates_full(tmp_path):
    scripted = ScriptedState(tmp_path)
    res = eval_mod.run_suite(SUITE, exec_fn=scripted)
    assert [t["id"] for t in res["tasks"]] == ["lh1", "lh2", "lh3"]
    assert res["pass_rate"] == 1.0
    assert res["fix_rate"] == 1.0
    for t in res["tasks"]:
        assert t["fix_rate"] == 1.0 and t["checks_total"] >= 2


def test_order_dependence_control_lh2_first_fails(tmp_path):
    """The discriminating run: lh2 alone in a fresh workspace."""
    scripted = ScriptedState(tmp_path)
    tmp_suite = tmp_path / "lh2only.yaml"
    tmp_suite.write_text(
        "name: lh2-only\ntasks:\n"
        "  - id: lh2\n"
        "    prompt: >-\n"
        "      Multi-step job, step 2: read state/step1.txt from the previous\n"
        "      step and answer with exactly: step-two got ALPHA-BUILD\n"
        "    expect_stdout_contains: [\"step-two got ALPHA-BUILD\"]\n"
        "    expect_exit: 0\n"
        "    ephemeral: false\n")
    res = eval_mod.run_suite(tmp_suite, exec_fn=scripted)
    t = res["tasks"][0]
    assert t["ok"] is False and res["pass_rate"] == 0.0
    assert "step-two got ALPHA-BUILD" in t["detail"].get("missing_stdout", [])
    # Fix Rate tells the partial story: 1 of 2 declared checks (exit passed)
    assert t["fix_rate"] == 0.5 and t["checks_passed"] == 1


def test_fix_rate_two_of_three(tmp_path):
    suite = tmp_path / "two-of-three.yaml"
    suite.write_text(
        "name: partial\ntasks:\n"
        "  - id: p1\n"
        "    prompt: \"say ok\"\n"
        "    expect_stdout_contains: [\"ok\", \"never-present\"]\n"
        "    expect_exit: 0\n")

    def exec_fn(prompt, **kw):
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": "ok"}})
        return 0

    res = eval_mod.run_suite(suite, exec_fn=exec_fn)
    t = res["tasks"][0]
    assert t["ok"] is False and res["pass_rate"] == 0.0
    assert (t["checks_passed"], t["checks_total"]) == (2, 3)
    assert t["fix_rate"] == 0.667
    assert res["fix_rate"] == 0.667


def test_empty_suite_fix_rate_is_none_not_zero(tmp_path):
    suite = tmp_path / "empty.yaml"
    suite.write_text("name: empty\ntasks: []\n")
    res = eval_mod.run_suite(suite, exec_fn=lambda *a, **k: 0)
    assert res["fix_rate"] is None
    assert res["pass_rate"] == 0.0
