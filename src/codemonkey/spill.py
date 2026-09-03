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


def spill(output: str, *, tool: str = "shell") -> Path:
    """Write output verbatim to a spill file; returns its path."""
    h = hashlib.sha256(f"{tool}:{output}".encode()).hexdigest()[:16]
    p = spill_dir() / f"{time.strftime('%Y%m%d-%H%M%S')}-{tool}-{h}.txt"
    p.write_text(output)
    return p


def truncate_with_spill(output: str, budget: int, *, tool: str = "shell",
                        head_frac: float = 0.6) -> str:
    """Cycle-17-compatible truncation, with a spill pointer when the output
    exceeds budget. Under budget -> unchanged. Over budget -> head+tail with
    PARTIAL marker carrying the spill path."""
    if len(output) <= budget:
        return output
    path = spill(output, tool=tool)
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
