"""Capability ladder + task segmentation (loop 42, cycles 99–100).

R-G, up front: the tool-use ladder is BFCL
(https://gorilla.cs.berkeley.edu/leaderboard.html) — frontier models far
above any 27B-class open-weight entry, and BFCL is single-call accuracy, an
easier game than multi-turn coordination. Our tiers below are deliberately
smaller than BFCL's: they ask what THIS endpoint clears, not what the
frontier clears. "Segmentation buys +N points and the long-horizon tier is
still out of reach" remains a valid exit.

TIERS (each: prompt + file-system checker — deterministic, no model judge):
- L1 single-call: one correct write_file call.
- L2 multi-call: three writes, order-free, one turn or several.
- L3 multi-turn with state: read in.txt, write its double to out.txt —
  the provider must USE an observation.

`run_ladder(provider, workdir)` drives each tier through `run_turns`
(prompt protocol) and reports pass + malformed counts per tier. It measures
any provider — scripted fakes in tests, the live endpoint when reachable.

SEGMENTATION (C100): `run_segmented` runs hand-specified segments as
separate short-horizon runs with explicit handoff (files + handoff.json),
per-segment checks, stop-on-first-failure. Per-segment TOOL RESTRICTION is
NOT built here — R42 ASK 1 pending; the surface is identical in every
segment and the report says so.
"""

from __future__ import annotations

from pathlib import Path


def _ctx(workdir: Path):
    from .sandbox import ToolContext

    return ToolContext(workdir=Path(workdir).resolve(),
                       sandbox="danger-full-access")


def _run_tier(provider, workdir: Path, prompt: str, max_turns: int,
              needles: list) -> dict:
    from .loop import run_turns

    events: list = []
    turn = run_turns(provider, prompt, _ctx(workdir),
                     tool_protocol="prompt", max_turns=max_turns,
                     journal_thread="", journal_run="",
                     redact_needles=needles,
                     on_event=events.append)
    mal = sum(1 for e in events
              if isinstance(e, dict) and e.get("type") == "tool.completed"
              and e.get("error_class") in ("schema_mismatch", "parse"))
    calls = sum(1 for e in events
                if isinstance(e, dict) and e.get("type") == "tool.completed")
    return {"turn": turn, "events": events, "tool_calls": calls,
            "malformed": mal}


def _check_l1(workdir: Path) -> bool:
    p = workdir / "answer.txt"
    return p.is_file() and p.read_text().strip() == "42"


def _check_l2(workdir: Path) -> bool:
    return all((workdir / f"{c}.txt").is_file()
               and (workdir / f"{c}.txt").read_text().strip() == c
               for c in ("a", "b", "c"))


def _check_l3(workdir: Path) -> bool:
    try:
        want = int((workdir / "in.txt").read_text().strip()) * 2
    except (OSError, ValueError):
        return False
    p = workdir / "out.txt"
    try:
        return p.is_file() and int(p.read_text().strip()) == want
    except (OSError, ValueError):
        return False


TIERS = [
    {"id": "L1", "name": "single-call",
     "prompt": "Write the number 42 (just 42) to answer.txt.",
     "check": _check_l1, "max_turns": 3},
    {"id": "L2", "name": "multi-call",
     "prompt": "Create a.txt containing a, b.txt containing b, c.txt containing c.",
     "check": _check_l2, "max_turns": 6},
    {"id": "L3", "name": "multi-turn-state",
     "prompt": "Read the integer in in.txt, double it, write the result to out.txt.",
     "check": _check_l3, "max_turns": 6},
]


def run_ladder(provider, workdir, *, needles=None) -> dict:
    """Run all tiers. Returns per-tier {pass, tool_calls, malformed}."""
    workdir = Path(workdir).resolve()
    if not (workdir / "in.txt").exists():
        (workdir / "in.txt").write_text("21")
    out: dict = {"tiers": {}}
    for tier in TIERS:
        # Isolate tiers: L2's files must come from L2's run, not L1's.
        tdir = workdir / f"_tier_{tier['id']}"
        tdir.mkdir(exist_ok=True)
        if tier["id"] == "L3":
            (tdir / "in.txt").write_text("21")
        res = _run_tier(provider, tdir, tier["prompt"], tier["max_turns"],
                        needles or [])
        out["tiers"][tier["id"]] = {
            "name": tier["name"],
            "pass": bool(tier["check"](tdir)),
            "tool_calls": res["tool_calls"],
            "malformed": res["malformed"],
        }
    passed = sum(1 for t in out["tiers"].values() if t["pass"])
    out["cleared"] = f"{passed}/{len(TIERS)}"
    out["total_malformed"] = sum(t["malformed"]
                                 for t in out["tiers"].values())
    return out


def run_segmented(provider_factory, segments: list, workdir,
                  *, needles=None) -> dict:
    """Run hand-specified segments as separate short runs with handoff.

    segments: [{id, prompt, check(workdir)->bool}]. Each segment runs in a
    shared workdir (files ARE the handoff) plus handoff.json recording per-
    segment completion. Stop on first failed check. No tool restriction
    (R42 ASK 1 pending) — identical surface every segment, stated here.
    """
    import json

    workdir = Path(workdir).resolve()
    results = []
    for seg in segments:
        provider = provider_factory(seg["id"])
        res = _run_tier(provider, workdir, seg["prompt"], seg.get(
            "max_turns", 6), needles or [])
        ok = bool(seg["check"](workdir))
        results.append({"id": seg["id"], "pass": ok,
                        "tool_calls": res["tool_calls"],
                        "malformed": res["malformed"]})
        (workdir / "handoff.json").write_text(json.dumps(
            {"completed": [r["id"] for r in results if r["pass"]]}))
        if not ok:
            break
    return {"segments": results,
            "cleared": f"{sum(1 for r in results if r['pass'])}/{len(segments)}",
            "total_malformed": sum(r["malformed"] for r in results),
            "tool_restriction": "none (R42 ASK 1 pending)"}
