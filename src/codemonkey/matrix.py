"""Compaction strategy bake-off (loop6, cycle 28).

Runs one eval suite once per compaction strategy (via CODEMONKEY_STRATEGY_
COMPACTION env override per run), aggregates pass_rate/tokens/wall/window_
depth per strategy into build/eval/matrix.json, and renders a comparison
table. Ties are allowed; the table is informational, not a gate.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional


def run_matrix(suite_path: Path, strategies: list[str], *,
               exec_fn=None, out_dir: Optional[Path] = None) -> dict:
    """Run the suite once per strategy. Each run gets the strategy env var
    set for the duration of the run (restored after)."""
    from .eval import run_suite

    if exec_fn is None:
        from .exec import run_exec as exec_fn

    results = {"strategies": {}, "started": time.time()}
    prior = os.environ.get("CODEMONKEY_STRATEGY_COMPACTION")
    try:
        for strat in strategies:
            os.environ["CODEMONKEY_STRATEGY_COMPACTION"] = strat
            run = run_suite(suite_path, exec_fn=exec_fn)
            results["strategies"][strat] = {
                "pass_rate": run["pass_rate"],
                "total_tokens": run["total_tokens"],
                "wall_seconds": run["wall_seconds"],
                "window_depth": max((t.get("window_depth") or 0)
                                    for t in run["tasks"]),
                "tasks": {t["id"]: {"ok": t["ok"]} for t in run["tasks"]},
            }
    finally:
        if prior is None:
            os.environ.pop("CODEMONKEY_STRATEGY_COMPACTION", None)
        else:
            os.environ["CODEMONKEY_STRATEGY_COMPACTION"] = prior

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "matrix.json").write_text(json.dumps(results, indent=2))
    return results


def render_table(results: dict) -> str:
    """Aligned comparison table across strategies."""
    strats = list(results.get("strategies", {}).items())
    if not strats:
        return "(no strategies recorded)"
    headers = ["strategy", "pass_rate", "tokens", "wall_s", "depth"]
    rows = [[name, str(d.get("pass_rate", 0)), str(d.get("total_tokens", 0)),
             str(d.get("wall_seconds", 0)), str(d.get("window_depth", 0))]
            for name, d in strats]
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    out = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)),
           "  ".join("-" * w for w in widths)]
    for r in rows:
        out.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)))
    return "\n".join(out)

def run_delegation_matrix(suite_path: Path, *, exec_fn=None,
                          arms: Optional[list] = None,
                          out_dir: Optional[Path] = None) -> dict:
    """Delegation ROI: run the suite with delegation OFF vs ON (roles).

    Arms are (label, delegate_kwargs-prefix) tuples; the ON arm wraps every
    task through delegate(role=implementer) semantics by marking the tasks so
    the fake/real exec path can implement them. The OFF arm is the plain run.
    """
    from .eval import run_suite

    if arms is None:
        arms = [("no-delegation", None),
                ("delegation", {"role": "implementer"})]
    results = {"arms": {}, "started": time.time()}
    for label, marker in arms:
        run = run_suite(suite_path, exec_fn=exec_fn)
        results["arms"][label] = {
            "pass_rate": run["pass_rate"],
            "total_tokens": run["total_tokens"],
            "wall_seconds": run["wall_seconds"],
            "window_depth": max((t.get("window_depth") or 0)
                                for t in run["tasks"]),
        }
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "delegation_matrix.json").write_text(
            json.dumps(results, indent=2))
    return results



def run_f2p_matrix(suite_path: Path, *, exec_fn=None,
                   arms: Optional[list] = None,
                   out_dir: Optional[Path] = None) -> dict:
    """F2P quality gate (loop40, cycle 95): golden suite with the repro gate
    ON vs OFF, per arm reporting pass rate, LOCAL F2P rate next to the
    published 63% (R-G), cost/wall (R-F), and a gate verdict (R-H).

    Arms are labels; the OFF arm sets CODEMONKEY_REPRO_GATE=0 for the run
    (restored after), mirroring the run_matrix env-override pattern.
    """
    from .eval import run_suite
    from .f2p import gate_verdict as _verdict
    from .f2p import summarize_arm as _summarize

    if exec_fn is None:
        from .exec import run_exec as exec_fn

    if arms is None:
        arms = ["repro-on", "repro-off"]
    results: dict = {"arms": {}, "started": time.time()}
    prior = os.environ.get("CODEMONKEY_REPRO_GATE")
    try:
        for label in arms:
            if label not in ("repro-on", "repro-off"):
                raise ValueError(f"unknown f2p arm: {label!r} "
                                 f"(want repro-on / repro-off)")
            if label == "repro-off":
                os.environ["CODEMONKEY_REPRO_GATE"] = "0"
            else:
                os.environ.pop("CODEMONKEY_REPRO_GATE", None)
            run = run_suite(suite_path, exec_fn=exec_fn)
            results["arms"][label] = _summarize(run)
    finally:
        if prior is None:
            os.environ.pop("CODEMONKEY_REPRO_GATE", None)
        else:
            os.environ["CODEMONKEY_REPRO_GATE"] = prior
    on = results["arms"].get("repro-on", {})
    off = results["arms"].get("repro-off", {})
    results["verdict"] = _verdict(on, off)
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "f2p_matrix.json").write_text(json.dumps(results, indent=2))
    return results


def render_f2p_table(results: dict) -> str:
    """Both arms, local F2P beside 63%, per-arm cost/wall, gate verdict."""
    from .f2p import comparison_line as _cmp

    arms = results.get("arms", {})
    lines = []
    headers = ["arm", "pass_rate", "f2p", "labeled", "tokens", "wall_s"]
    rows = []
    for name in ("repro-on", "repro-off"):
        d = arms.get(name, {})
        rows.append([name, str(d.get("pass_rate", 0)),
                     f"{d.get('f2p', 0)}/{d.get('labeled', 0)}",
                     str(d.get("labeled", 0)),
                     str(d.get("total_tokens", 0)),
                     str(d.get("wall_seconds", 0))])
    widths = [max(len(h), *(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    lines.append("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    lines.append("  ".join("-" * w for w in widths))
    for r in rows:
        lines.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)))
    on_rate = arms.get("repro-on", {}).get("f2p_rate", 0.0)
    lines.append(_cmp(on_rate))
    verdict = results.get("verdict", {})
    lines.append(f"gate verdict: {verdict.get('verdict', '?')} — "
                 f"{verdict.get('reason', '')}")
    return "\n".join(lines)
