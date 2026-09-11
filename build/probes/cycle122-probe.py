"""CYCLE 122 R-I probe — the long-horizon suite + Fix Rate, through the CLI.

(a) `codemonkey eval build/suites/long-horizon.yaml` (in-process CliRunner,
    real run_suite, scripted exec standing in for the model): all three
    order-dependent tasks pass; the printed suite line carries
    `fix_rate: 1.0` and every task line carries its own fix_rate.
(b) the ORDER-DEPENDENCE control through the same interface: lh2 alone in a
    fresh workspace → `[FAIL] lh2  fix_rate=0.5 (1/2)` with the missing
    needle in the detail line.
(c) the 2-of-3 fixture → suite line `fix_rate: 0.667`, pass_rate 0.

Usage:  uv run python build/probes/cycle122-probe.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAIL
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL = 1


class ScriptedState:
    def __init__(self, workdir: Path):
        self.wd = workdir

    def __call__(self, prompt, **kw):
        state1 = self.wd / "state" / "step1.txt"
        msg = ""
        if "step 1" in prompt:
            state1.parent.mkdir(parents=True, exist_ok=True)
            state1.write_text("ALPHA-BUILD")
            msg = "step-one done (ALPHA-BUILD)"
        elif "step 2" in prompt:
            msg = ("step-two got ALPHA-BUILD" if state1.exists()
                   else "step-two got nothing (no artifact)")
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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cm122-"))
    os.environ["HOME"] = str(tmp / ".home")
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)

    import codemonkey.exec as exec_mod
    exec_mod.run_exec = ScriptedState(tmp / "ws")  # the REAL harness path

    from typer.testing import CliRunner
    from codemonkey.cli import app as cli_app

    runner = CliRunner()
    suite = ROOT / "build" / "suites" / "long-horizon.yaml"

    print("--- 1. the real suite, in order, through the CLI ---")
    r = runner.invoke(cli_app, ["eval", str(suite), "--out", str(tmp / "out1")])
    out = r.output or ""
    print(out.rstrip())
    check("exit 0", r.exit_code == 0, f"exit={r.exit_code}")
    check("suite line carries fix_rate: 1.0", "fix_rate: 1.0" in out)
    check("tasks ran in order", out.find("[PASS] lh1") < out.find("[PASS] lh2")
          < out.find("[PASS] lh3"))
    check("per-task fix lines", "[PASS] lh1  fix_rate=1.0 (3/3)" in out
          and "[PASS] lh3  fix_rate=1.0 (2/2)" in out)

    print("--- 2. order-dependence control: lh2 alone, fresh workspace ---")
    exec_mod.run_exec = ScriptedState(tmp / "ws2")     # fresh: no artifact
    lh2 = tmp / "lh2only.yaml"
    lh2.write_text(
        "name: lh2-only\ntasks:\n"
        "  - id: lh2\n"
        "    prompt: >-\n"
        "      Multi-step job, step 2: read state/step1.txt from the previous\n"
        "      step and answer with exactly: step-two got ALPHA-BUILD\n"
        "    expect_stdout_contains: [\"step-two got ALPHA-BUILD\"]\n"
        "    expect_exit: 0\n"
        "    ephemeral: false\n")
    r2 = runner.invoke(cli_app, ["eval", str(lh2), "--out", str(tmp / "out2")])
    out2 = r2.output or ""
    print(out2.rstrip())
    check("lh2 first → FAIL with fix_rate 0.5 (1/2)",
          "[FAIL] lh2  fix_rate=0.5 (1/2)" in out2)
    check("missing needle named",
          "step-two got ALPHA-BUILD" in out2 and "missing_stdout" in out2)

    print("--- 3. 2-of-3 fixture: fix_rate 0.667, pass_rate 0 ---")
    def exec_two_of_three(prompt, **kw):
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": "ok"}})
        return 0
    exec_mod.run_exec = exec_two_of_three
    p3 = tmp / "two-of-three.yaml"
    p3.write_text(
        "name: partial\ntasks:\n"
        "  - id: p1\n"
        "    prompt: \"say ok\"\n"
        "    expect_stdout_contains: [\"ok\", \"never-present\"]\n"
        "    expect_exit: 0\n")
    r3 = runner.invoke(cli_app, ["eval", str(p3), "--out", str(tmp / "out3")])
    out3 = r3.output or ""
    print(out3.rstrip())
    check("suite fix_rate 0.667, pass_rate 0.0",
          "pass_rate: 0.0" in out3 and "fix_rate: 0.667" in out3)
    check("task line 2/3", "[FAIL] p1  fix_rate=0.667 (2/3)" in out3)

    print()
    print("CYCLE122 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
