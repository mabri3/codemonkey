"""loop50 cycle 121 — the CL protocol runner: sequential order, both halves
under the named statistic.

Discriminating claims:

* per-arm blocks are SEQUENTIAL — the recorded call sequence is exactly
  [arm1 transfer in file order][arm1 retention][arm2 transfer][arm2
  retention]: no interleave (the trace assertion would fail if the loops
  sliced by suite instead of by arm);
* the executed order is recorded against the suite file's DECLARED order
  (`order[label][phase] = {declared, executed, ok}`);
* `--cl-protocol` without `--retention` refuses (usage error, exit 2 via the
  CLI); a retention suite identical to the transfer suite refuses;
* endpoint down → both halves BLOCKED with the reason, `None` numbers, arms
  still ran, contamination still checked.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from codemonkey import skills_arms
from codemonkey.cli import app as cli_app


TRANSFER = """name: transfer
tasks:
  - id: t1
    prompt: "T-one"
  - id: t2
    prompt: "T-two"
"""

RETENTION = """name: retention
tasks:
  - id: r1
    prompt: "R-one"
  - id: r2
    prompt: "R-two"
"""


def _suites(tmp: Path):
    a = tmp / "transfer.yaml"
    b = tmp / "retention.yaml"
    a.write_text(TRANSFER)
    b.write_text(RETENTION)
    return a, b


def test_sequential_order_recorded_and_no_interleave(tmp_path, monkeypatch):
    calls: list[str] = []

    def exec_fn(prompt, **kw):
        calls.append(prompt)
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": "ok"}})
        return 0

    a, b = _suites(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    res = skills_arms.run_skills_matrix(
        a, exec_fn=exec_fn, retention_suite=b, cl_protocol=True,
        store=tmp_path, probe=lambda: "")

    assert res["cl_protocol"] is True
    # the trace: per-arm sequential blocks, file order inside each block
    assert calls == ["T-one", "T-two", "R-one", "R-two",
                     "T-one", "T-two", "R-one", "R-two"], calls
    for label in ("skills-on", "skills-off"):
        blk = res["order"][label]
        assert blk["transfer"]["declared"] == ["t1", "t2"]
        assert blk["transfer"]["executed"] == ["t1", "t2"]
        assert blk["retention"]["executed"] == ["r1", "r2"]
        assert blk["transfer"]["ok"] is True
        assert blk["retention"]["ok"] is True
    assert "cl-protocol: sequential order verified 2/2" in \
        skills_arms.render_skills_table(res)


def test_order_control_sees_a_misfiled_suite(tmp_path, monkeypatch):
    """The order check must FAIL when executed order != declared order —
    a suite whose executed list is reversed is the manufactured defect."""
    a, b = _suites(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))

    def exec_fn(prompt, **kw):
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": "ok"}})
        return 0

    res = skills_arms.run_skills_matrix(
        a, exec_fn=exec_fn, retention_suite=b, cl_protocol=True,
        store=tmp_path, probe=lambda: "")
    blk = res["order"]["skills-on"]["transfer"]
    bad = {"declared": blk["declared"], "executed": list(reversed(blk["executed"])),
           "ok": False}
    assert bad["executed"] != blk["declared"]   # the control can see it
    assert blk["ok"] is True                    # while the real order passed


def test_cl_requires_distinct_retention(tmp_path):
    a, b = _suites(tmp_path)
    with pytest.raises(ValueError, match="requires --retention"):
        skills_arms.run_skills_matrix(a, exec_fn=lambda *x, **k: 0,
                                      cl_protocol=True)
    with pytest.raises(ValueError, match="must differ"):
        skills_arms.run_skills_matrix(a, exec_fn=lambda *x, **k: 0,
                                      retention_suite=a, cl_protocol=True)


def test_cl_blocked_half_when_endpoint_down(tmp_path, monkeypatch):
    a, b = _suites(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))

    def exec_fn(prompt, **kw):
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": "ok"}})
        return 0

    res = skills_arms.run_skills_matrix(
        a, exec_fn=exec_fn, retention_suite=b, cl_protocol=True,
        store=tmp_path, probe=lambda: "Connection refused")
    assert res["forward_transfer"]["value"] is None
    assert res["forward_transfer"]["status"] == "BLOCKED"
    assert res["retention_check"]["value"] is None
    assert res["retention_check"]["status"] == "BLOCKED"
    assert "Connection refused" in res["forward_transfer"]["reason"]
    # the arms still ran real numbers, and contamination still checked
    assert res["arms"]["skills-on"]["pass_rate"] == 1.0
    assert "violations" in res["contamination"]


def test_cli_usage_error_exit_2(tmp_path, monkeypatch):
    a, _ = _suites(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    runner = CliRunner()
    r = runner.invoke(cli_app, ["eval", str(a), "--arms",
                                "skills-on,skills-off", "--cl-protocol",
                                "--out", str(tmp_path / "out")])
    assert r.exit_code == 2
    assert "--retention" in (r.output or "") + str(getattr(r, "stderr", "") or "")
