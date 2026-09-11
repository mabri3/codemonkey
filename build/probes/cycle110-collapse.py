"""CYCLE 110 R-I probe — the 50-round collapse regression, end to end.

Fifty rounds of synthetic deltas go through the REAL merge path; the round-1
entry must be byte-stable and the store monotone. Then the released CLI
exercises `playbook stats` and `playbook merge`. Finally a REWRITE-style
control (keep-last-10 + truncate — the ACE case-study shape) is run through
the same 50 rounds and must LOSE its round-1 entry: the regression can see
the defect it exists for.

Usage:  uv run python build/probes/cycle110-collapse.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

ROUNDS = 50
FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAIL
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL = 1


PROV = {"run_id": "probe110", "session_id": "s", "taint_free": True}


def deltas_for(r: int) -> list[dict]:
    out = [
        {"kind": "strategy", "section": "growth",
         "text": f"round {r} rule", "provenance": dict(PROV)},
        {"kind": "pitfall", "section": "recurring",
         "text": "recurring lesson alpha", "provenance": dict(PROV)},
    ]
    if r % 10 == 9:
        out.append({"kind": "pitfall", "section": "recurring",
                    "text": "recurring  lesson   alpha", "provenance": dict(PROV)})
    return out


def main() -> int:
    from codemonkey import playbook

    tmp = Path(tempfile.mkdtemp(prefix="cm110-"))
    ws = tmp / "ws"
    ws.mkdir()
    os.environ["HOME"] = str(tmp / ".home")

    print("--- 1. fifty rounds through the REAL merge path ---")
    r0id = playbook.entry_id("strategy", "growth", "round 0 rule")
    words_by_round = {}
    round0_bytes = None
    for r in range(ROUNDS):
        playbook.merge_deltas(ws, deltas_for(r))
        if r == 0:
            round0_bytes = json.dumps(
                [e for e in playbook.list_entries(ws) if e["id"] == r0id][0],
                sort_keys=True)
        if r in (0, 24, 49):
            words_by_round[r] = playbook.store_stats(ws)["words"]
    print(f"  words after rounds 1/25/50: {words_by_round}")
    st = playbook.store_stats(ws)
    print(f"  stats: {json.dumps(st)}")

    e = [e for e in playbook.list_entries(ws) if e["id"] == r0id][0]
    check("round-1 entry byte-stable after 50 rounds",
          json.dumps(e, sort_keys=True) == round0_bytes)
    check("no duplicates, one entry per distinct delta",
          st["entries"] == ROUNDS + 1, f"entries={st['entries']}")
    check("recurring counter 50 + 5 whitespace twins",
          [x for x in playbook.list_entries(ws)
           if x["text"] == "recurring lesson alpha"][0]["counter"] == ROUNDS + 5)
    check("growth monotone (never shrinks)",
          words_by_round[0] <= words_by_round[24] <= words_by_round[49])

    print("--- 2. released CLI: stats + one more merge ---")
    env = dict(os.environ)
    cm = ["uv", "run", "--quiet", "--project", str(ROOT), "codemonkey"]
    r1 = subprocess.run(cm + ["playbook", "stats"], cwd=ws, env=env,
                        capture_output=True, text=True)
    print(f"  {r1.stdout.strip()}")
    check("CLI stats exits 0 and reports 51 entries",
          r1.returncode == 0 and "entries=51" in r1.stdout)
    extra = ws / "extra.json"
    extra.write_text(json.dumps({"deltas": [
        {"kind": "schema", "section": "cli", "text": "cli merged this",
         "provenance": dict(PROV)}]}))
    r2 = subprocess.run(cm + ["playbook", "merge", str(extra)], cwd=ws, env=env,
                        capture_output=True, text=True)
    print(f"  {r2.stdout.strip()}")
    check("CLI merge adds the 52nd entry", r2.returncode == 0 and "added=1" in r2.stdout)
    r3 = subprocess.run(cm + ["playbook", "stats"], cwd=ws, env=env,
                        capture_output=True, text=True)
    check("stats follows the CLI merge", "entries=52" in r3.stdout)

    print("--- 3. the REWRITE-style control must fail the regression ---")
    ctl: list[dict] = []

    def ctl_merge(r: int) -> None:
        for d in deltas_for(r):
            eid = playbook.entry_id(d["kind"], d["section"], d["text"])
            ex = next((x for x in ctl if x["id"] == eid), None)
            if ex is None:
                ctl.append({"id": eid, "text": d["text"], "counter": 1})
            else:
                ex["counter"] += 1
        del ctl[:-10]                      # context collapse: forget the old
        for x in ctl:
            x["text"] = x["text"][:20].strip()   # brevity bias: truncate

    for r in range(ROUNDS):
        ctl_merge(r)
    ctl_has_round0 = any(x["id"] == r0id for x in ctl)
    print(f"  rewrite control: round-1 entry present after 50 rounds: "
          f"{ctl_has_round0}")
    check("the control's round-1 entry is GONE (regression sees the collapse)",
          not ctl_has_round0)

    print()
    print("CYCLE110 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
