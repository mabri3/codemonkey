"""F2P quality gate + measurement (loop 40, cycle 95).

"A test that never failed proves nothing": a generated test counts as
fix-evidence ONLY if a fail→pass transition was observed. Labels, from the
C93 `repro.verdict` trace record:

- F2P:      verdict VERIFIED (fail observed pre-patch, pass post-patch)
- UNPROVEN: verdict UNVERIFIED (pass-only, or fail never observed)
- N/A:      no verdict on the trace (gate off / no verifier configured)

R-G (stated UP FRONT, research-loop40): ~63% fail-to-pass is a FRONTIER
number — e-Otter++ reports 63.0% F2P on TDD-Bench Verified via
execution-feedback selection. This repo (single local 27B, no inference
scaling, no test-selection machinery) will NOT match it; local rates print
NEXT TO 63%, never as a chase.
"""

from __future__ import annotations

# R-G published number + provenance. Do not "update" this to a local
# measurement — the comparison direction is local-vs-frontier, always.
PUBLISHED_F2P = 0.63
PUBLISHED_F2P_SOURCE = "e-Otter++ 63.0% F2P on TDD-Bench Verified (frontier)"

F2P = "F2P"
UNPROVEN = "UNPROVEN"
NOT_APPLICABLE = "N/A"


def label_task(events: list) -> str:
    """Label one task's fix-evidence from its trace (last repro verdict)."""
    verdict = None
    for ev in events:
        if isinstance(ev, dict) and ev.get("type") == "repro.verdict":
            verdict = (ev.get("report") or {}).get("verdict")
    if verdict is None:
        return NOT_APPLICABLE
    return F2P if verdict == "VERIFIED" else UNPROVEN


def summarize_arm(run: dict) -> dict:
    """Per-arm aggregates: pass rate, F2P counts/rate, cost/wall (R-F)."""
    tasks = run.get("tasks", []) or []
    labeled = [t for t in tasks if t.get("f2p") in (F2P, UNPROVEN)]
    n_f2p = sum(1 for t in labeled if t.get("f2p") == F2P)
    return {
        "pass_rate": run.get("pass_rate", 0),
        "tasks": len(tasks),
        "labeled": len(labeled),
        "f2p": n_f2p,
        "f2p_rate": round(n_f2p / len(labeled), 3) if labeled else 0.0,
        "total_tokens": run.get("total_tokens", 0),
        "wall_seconds": run.get("wall_seconds", 0),
    }


def gate_verdict(on: dict, off: dict) -> dict:
    """R-H: is the ON-vs-OFF measurement decision-grade? Honest rules:

    - arms must have run the same task count, else INCONCLUSIVE (mismatched);
    - fewer than 3 labeled tasks in the ON arm → INCONCLUSIVE (too thin);
    - otherwise MEASURED with the direction of the pass-rate delta.
    The verdict never claims the gate *caused* a delta (no causal
    identification on one suite run) — it reports what was measured.
    """
    if on.get("tasks", 0) != off.get("tasks", 0) or not on.get("tasks"):
        return {"verdict": "INCONCLUSIVE",
                "reason": "arm task counts differ or suite empty"}
    if on.get("labeled", 0) < 3:
        return {"verdict": "INCONCLUSIVE",
                "reason": f"only {on.get('labeled', 0)} labeled tasks "
                          f"(need >= 3 for a reading)"}
    delta = round(on.get("pass_rate", 0) - off.get("pass_rate", 0), 3)
    direction = ("on-ahead" if delta > 0 else
                 "off-ahead" if delta < 0 else "tied")
    return {"verdict": "MEASURED", "direction": direction,
            "pass_rate_delta": delta,
            "reason": "observational delta on one suite run; not causal"}


def comparison_line(local_rate: float) -> str:
    """Local F2P next to the published number (R-G)."""
    gap = round(local_rate - PUBLISHED_F2P, 3)
    return (f"local F2P {local_rate:.3f} vs published {PUBLISHED_F2P:.2f} "
            f"({PUBLISHED_F2P_SOURCE}) — gap {gap:+.3f} (frontier reference, "
            f"not a target)")
