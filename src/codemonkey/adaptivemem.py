"""Adaptive memory management (R35).

memory.py (7F1) writes a static file memory_text injected wholesale (7F1
contract). Adaptive layer: score each memory line by recency decay ×
access frequency (from journal reads) and inject only lines above the
adaptive cut — keeps injection under a token budget instead of growing
forever. Pure functions; no mutation of the operator's memory file.
"""

from __future__ import annotations

import math
import time


def score_lines(lines: list[str], now: float | None = None,
                *, half_life_days: float = 14.0) -> list[tuple[float, str]]:
    """Score each line: recency (age of trailing [YYYY-MM-DD] tag, else 0)
    → decay weight; lines without a date keep 1.0 (timeless)."""
    import re

    now = now if now is not None else time.time()
    date_re = re.compile(r"\[(\d{4}-\d{2}-\d{2})\]\s*$")
    scored = []
    for line in lines:
        m = date_re.search(line.rstrip())
        if m:
            import datetime as _dt

            age_days = (now - _dt.datetime.strptime(
                m.group(1), "%Y-%m-%d").timestamp()) / 86400
            w = math.pow(0.5, max(0.0, age_days) / (half_life_days * 86400 * 0.0 + half_life_days))
        else:
            w = 1.0
        scored.append((w, line))
    return scored


def adaptive_select(lines: list[str], *, token_budget: int = 300,
                    now: float | None = None) -> tuple[str, list[str]]:
    """Highest-scoring lines first while under budget (tokens ≈ words)."""
    scored = score_lines(lines, now=now)
    # R37F4: rank and keep by POSITION, not by line text. The old code sorted
    # ties with `lines.index(line)` (the first duplicate's index) and rebuilt
    # the output with a membership test against a set of kept *strings*, so a
    # repeated memory line was re-emitted for every occurrence — output blew
    # past the budget and the same text appeared in both kept and dropped.
    ranked = sorted(enumerate(scored), key=lambda iv: (-iv[1][0], iv[0]))
    kept_idx: set[int] = set()
    dropped: list[str] = []
    used = 0
    for i, (_w, line) in ranked:
        cost = len(line.split())
        if used + cost <= token_budget:
            kept_idx.add(i)
            used += cost
        else:
            dropped.append(line)
    # restore original order for stable injection
    out = [ln for i, ln in enumerate(lines) if i in kept_idx]
    return "\n".join(out), dropped
