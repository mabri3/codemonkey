"""Anytime-valid sequential certificates (R30, Hoeffding-style m-statistics).

eval can stop EARLY with a certificate instead of a fixed N: after each task,
compute a confidence sequence on the pass rate; if it settles above/below the
threshold, stop and record the certificate. Client-side, deterministic.
"""

from __future__ import annotations

import math
from typing import Optional


def m_certificate(ok_flags: list[bool], delta: float = 0.05) -> Optional[bool]:
    """After observing ok[i] sequence (1 = pass), is P(pass) > 1/2 certified
    at level delta (anytime-valid)? None = not yet decided."""
    if not ok_flags:
        return None
    s = sum(1 for o in ok_flags if o)
    n = len(ok_flags)
    # Hoeffding-style: |s/n - 1/2| > sqrt(ln(1/delta)/(2n)) certifies direction
    margin = math.sqrt(math.log(1.0 / delta) / (2 * n))
    rate = s / n
    if rate - 0.5 > margin:
        return True
    if 0.5 - rate > margin:
        return False
    return None


def sequential_verdict(outcomes: list[bool], *, delta: float = 0.05,
                       min_n: int = 2) -> dict:
    """Replay outcomes one at a time; return the earliest certificate."""
    for i in range(min_n, len(outcomes) + 1):
        cert = m_certificate(outcomes[:i], delta=delta)
        if cert is not None:
            return {"certified_pass": cert, "at_n": i, "total": len(outcomes),
                    "stopped_early": i < len(outcomes)}
    return {"certified_pass": None, "at_n": None, "total": len(outcomes),
            "stopped_early": False}
