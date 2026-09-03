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
