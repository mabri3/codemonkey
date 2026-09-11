"""Tool-result spill (loop6, cycle 30).

When a tool output exceeds the observation budget, the cycle-17 behavior
truncates with a PARTIAL marker — and the model often re-runs the command.
Instead: spill the FULL output verbatim to ~/.codemonkey/spill/<hash>.txt and
return head + tail + a pointer. The model can then read_file/search the exact
region it needs instead of re-executing.

Spill files are pruned after 24h (configurable via spill_ttl_hours).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


def spill_dir() -> Path:
    d = Path.home() / ".codemonkey" / "spill"
    d.mkdir(parents=True, exist_ok=True)
    return d


def spill(output: str, *, tool: str = "shell", taint: dict | None = None) -> Path:
    """Write output verbatim to a spill file; returns its path.

    loop49 C118: when the spilled output is untrusted-derived (`taint` with
    `tainted: true`), a SIDECAR `<file>.taint.json` records its sources —
    reading the spill back later re-derives the taint from the sidecar, so a
    rewrite onto disk cannot launder it. The file content is untouched."""
    h = hashlib.sha256(f"{tool}:{output}".encode()).hexdigest()[:16]
    p = spill_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{tool}-{h}.txt"
    p.write_text(output)
    if taint and taint.get("tainted"):
        sidecar = p.with_name(p.name + ".taint.json")
        sidecar.write_text(json.dumps({
            "sources": list(taint.get("sources") or []),
            "tainted": True,
            "at": time.time(),
        }) + "\n")
    return p


def taint_for_path(path) -> dict | None:
    """The taint a spill path carries per its sidecar, or None. A path that
    is not a spill (or whose spill was clean) has no sidecar."""
    p = Path(path)
    sidecar = p.with_name(p.name + ".taint.json")
    if not sidecar.exists():
        return None
    try:
        data = json.loads(sidecar.read_text())
    except (OSError, ValueError):
        return {"sources": [], "tainted": True, "note": "unreadable sidecar — treated as tainted"}
    return data


def truncate_with_spill(output: str, budget: int, *, tool: str = "shell",
                        head_frac: float = 0.6,
                        taint: dict | None = None) -> str:
    """Cycle-17-compatible truncation, with a spill pointer when the output
    exceeds budget. Under budget -> unchanged. Over budget -> head+tail with
    PARTIAL marker carrying the spill path (and, when `taint` says the
    content is untrusted-derived, a sidecar — loop49 C118)."""
    if len(output) <= budget:
        return output
    path = spill(output, tool=tool, taint=taint)
    keep = max(1, budget - 120)  # room for marker + path
    head = int(keep * head_frac)
    tail = keep - head
    return (
        output[:head]
        + f"\n...[PARTIAL: {len(output)} chars total; full output saved to {path} — "
        + "use read_file or search on that path for the rest]\n"
        + (output[-tail:] if tail > 0 else "")
    )


def prune(max_age_hours: float = 24.0) -> int:
    """Delete spill files older than max_age_hours. Returns count removed."""
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for p in spill_dir().glob("*.txt"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        except OSError:
            continue
    return removed
