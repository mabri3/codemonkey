"""Tool-output slimming (loop8, cycle 35).

Deterministic, LLM-free noise reduction applied BEFORE the observation
budget: collapse 3+ consecutive blank lines to one, strip trailing
whitespace per line, drop ANSI escape sequences. Returns (slimmed, stats)
where stats records chars saved — journaled with the outcome.
"""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_BLANK3_RE = re.compile(r"\n{3,}")
_TRAIL_WS_RE = re.compile(r"[ \t]+$", re.M)


def slim(output: str, *, min_chars: int = 200) -> tuple[str, dict]:
    """Slim an output string. Outputs under min_chars pass untouched."""
    if len(output) < min_chars:
        return output, {"chars_saved": 0, "applied": False}
    orig = len(output)
    out = _ANSI_RE.sub("", output)
    out = _TRAIL_WS_RE.sub("", out)
    out = _BLANK3_RE.sub("\n\n", out)
    saved = orig - len(out)
    return out, {"chars_saved": saved, "applied": saved > 0}
