"""CYCLE 121 R-I probe — the CL protocol, end to end.

(a) In-process CL run (real run_skills_matrix + scripted exec): the recorded
    call trace is per-arm sequential blocks in suite file order; the executed
    order is checked against the DECLARED order for every block; with the
    endpoint probe reporting down, both halves are BLOCKED with the reason
    (None numbers), the arms still ran, contamination still checked.
(b) Released binary: `--cl-protocol` without `--retention` refuses with
    exit 2 and the reason.

Usage:  uv run python build/probes/cycle121-probe.py
"""

from __future__ import annotations

import os
import subprocess
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


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cm121-"))
    os.environ["HOME"] = str(tmp / ".home")
    Path(os.environ["HOME"]).mkdir(parents=True, exist_ok=True)

    a = tmp / "transfer.yaml"
    b = tmp / "retention.yaml"
    a.write_text(TRANSFER)
    b.write_text(RETENTION)

    from codemonkey import skills_arms

    calls: list[str] = []

    def exec_fn(prompt, **kw):
        calls.append(prompt)
        sink = kw.get("event_sink")
        if sink is not None:
            sink.append({"type": "item.completed",
                         "item": {"type": "agent_message", "text": "ok"}})
        return 0

    print("--- 1. sequential blocks, file order, order check ---")
    res = skills_arms.run_skills_matrix(
        a, exec_fn=exec_fn, retention_suite=b, cl_protocol=True,
        store=tmp, probe=lambda: "Connection refused (after 4 attempts)")
    check("trace: per-arm blocks, no interleave",
          calls == ["T-one", "T-two", "R-one", "R-two",
                    "T-one", "T-two", "R-one", "R-two"], str(calls))
    for label in ("skills-on", "skills-off"):
        blk = res["order"][label]
        check(f"{label}: transfer order ok ({blk['transfer']['executed']})",
              blk["transfer"]["ok"] is True)
        check(f"{label}: retention order ok ({blk['retention']['executed']})",
              blk["retention"]["ok"] is True)
    check("cl_protocol flag recorded", res["cl_protocol"] is True)
    rendered = skills_arms.render_skills_table(res)
    check("render names the CL order line",
          "cl-protocol: sequential order verified 2/2" in rendered)

    print("--- 2. BLOCKED halves; arms ran; contamination checked ---")
    check("forward transfer BLOCKED with reason + None",
          res["forward_transfer"]["status"] == "BLOCKED"
          and res["forward_transfer"]["value"] is None
          and "Connection refused" in res["forward_transfer"]["reason"])
    check("retention BLOCKED with reason + None",
          res["retention_check"]["status"] == "BLOCKED"
          and res["retention_check"]["value"] is None)
    check("arms produced real numbers anyway",
          res["arms"]["skills-on"]["pass_rate"] == 1.0
          and res["arms"]["skills-off"]["pass_rate"] == 1.0)
    check("contamination still checked", "violations" in res["contamination"])

    print("--- 3. released binary: usage refusal ---")
    env = dict(os.environ)
    p = subprocess.run(
        ["uv", "run", "--quiet", "--project", str(ROOT), "codemonkey",
         "eval", str(a), "--arms", "skills-on,skills-off", "--cl-protocol",
         "--out", str(tmp / "out")],
        capture_output=True, text=True, env=env, cwd=tmp)
    check("exit 2", p.returncode == 2, f"exit={p.returncode}")
    check("reason names --retention",
          "--retention" in (p.stdout + p.stderr),
          (p.stdout + p.stderr).strip()[:100])

    print()
    print("CYCLE121 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
