"""Pass-rate gate for eval early stopping (R30; R-H rename in loop 38/77).

R-H honesty statement (rule R-H: a certificate must be what it says it is):
``m_certificate`` is a fixed-n Hoeffding bound evaluated after every
observation — replaying a fixed-n bound over nested prefixes is NOT
anytime-valid inference (the error rate inflates across the growing prefix;
see the testing-by-betting / anytime-validity literature cited in
``build/loops-38-45-proposal.md``). It is therefore named for what it
actually is: ``hoeffding_gate``. Verdicts carry ``kind: "hoeffding-gate"``.
``sequential_verdict`` remains as a deprecated alias (one release) so
existing callers keep working with a warning. Loop-30-era numbers measured
under the old name are re-labeled, not re-measured (the bound is unchanged;
only the name and the validity claim changed) — see the cycle-77 BUILD_LOG
entry and the superseded note the capability register (cycle 81) carries.
"""

from __future__ import annotations

import math
import warnings
from typing import Optional


def m_certificate(ok_flags: list[bool], delta: float = 0.05) -> Optional[bool]:
    """Fixed-n Hoeffding bound at n = len(ok_flags): is P(pass) > 1/2
    certified at level delta? None = not yet decided at this n."""
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


def hoeffding_gate(outcomes: list[bool], *, delta: float = 0.05,
                   min_n: int = 2) -> dict:
    """Replay the fixed-n Hoeffding bound over nested prefixes; return the
    earliest gate verdict. ``kind`` names the statistic honestly (R-H)."""
    for i in range(min_n, len(outcomes) + 1):
        cert = m_certificate(outcomes[:i], delta=delta)
        if cert is not None:
            return {"kind": "hoeffding-gate", "certified_pass": cert,
                    "at_n": i, "total": len(outcomes),
                    "stopped_early": i < len(outcomes)}
    return {"kind": "hoeffding-gate", "certified_pass": None, "at_n": None,
            "total": len(outcomes), "stopped_early": False}


def sequential_verdict(outcomes: list[bool], *, delta: float = 0.05,
                       min_n: int = 2) -> dict:
    """Deprecated alias of :func:`hoeffding_gate` (loop 38, cycle 77, R-H).

    Kept for one release so existing callers keep working; emits a
    DeprecationWarning on every call and returns the identical verdict.
    """
    warnings.warn(
        "sequential_verdict is renamed to hoeffding_gate (the bound was "
        "always a fixed-n Hoeffding bound, not an anytime-valid sequential "
        "test); switch to hoeffding_gate",
        DeprecationWarning,
        stacklevel=2,
    )
    return hoeffding_gate(outcomes, delta=delta, min_n=min_n)
