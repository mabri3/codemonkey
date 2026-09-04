"""Stuck detector in the loop (loop 39, cycle 89 — report-only).

AgentRx frames looping-over-action as a TRAJECTORY property: no single
journal record carries it, so the detector lives in the turn loop where the
trajectory is visible. Rule (charter form): the same (tool, error_class)
failure pair repeated STREAK_THRESHOLD times in a row is `stuck`.

Report-only by charter (C89): the detector emits a `stuck` event, journals a
`stuck` outcome row, and appends a system nudge naming the failure. It NEVER
terminates the run — enforced stop is CYCLE 91 and waits on the user
(AWAITING-ASK). Set CODEMONKEY_STUCK=0 to disable the signal entirely.

The error_class is derived deterministically from the outcome tuple the loop
already has (same vocabulary failclass.py consumes): explicit meta
error_class > approval soft-deny > permission-rule deny > raised exception >
plain tool error. A successful call resets the streak.
"""

from __future__ import annotations

import os

STREAK_THRESHOLD = 3


def classify_outcome(name: str, ok: bool, output: str, meta: dict | None) -> str:
    """Deterministic error_class for one tool outcome ('' when ok)."""
    if ok:
        return ""
    meta = meta or {}
    for key in ("error_class",):
        if meta.get(key):
            return str(meta[key])
    if meta.get("approval") == "soft-deny":
        return "approval"
    if meta.get("rule") == "deny":
        return "auth"
    if meta.get("raised"):
        return "exception"
    out = str(output or "")
    if out.startswith("error:") or out.startswith("exit "):
        # "error:" = generic tool failure text; "exit N" = the shell tool's
        # failure convention (events.py parses it as the real exit code).
        return "tool-error"
    return "unknown"


def nudge_text(tool: str, error_class: str, streak: int, last_output: str) -> str:
    """The system nudge appended for the agent (never terminates)."""
    head = (last_output or "").strip().splitlines()[0][:200] if (last_output or "").strip() else "(no output)"
    return (
        f"STUCK: {tool} has failed {streak} times in a row "
        f"(failure kind: {error_class}). Last error: {head}. "
        "Do NOT repeat the same call — change the approach (different "
        "arguments, a different tool, or gather more information first), "
        "or finish with your best answer and report the blocker."
    )


class StuckDetector:
    """Consecutive-failure-pair tracker over one run's tool outcomes."""

    def __init__(self, threshold: int = STREAK_THRESHOLD):
        self.threshold = max(2, int(threshold))
        self._pair: tuple[str, str] | None = None
        self._streak = 0
        self._last_output = ""
        self.fired = 0  # times stuck fired this run (telemetry)

    def record(self, name: str, ok: bool, output: str,
               meta: dict | None = None) -> dict | None:
        """Feed one outcome. Returns the stuck signal on the threshold-th
        consecutive identical failure pair, else None."""
        cls = classify_outcome(name, ok, output, meta)
        if not cls:
            self._pair = None
            self._streak = 0
            return None
        pair = (name, cls)
        if pair == self._pair:
            self._streak += 1
        else:
            self._pair = pair
            self._streak = 1
        self._last_output = str(output or "")
        if self._streak == self.threshold:
            self.fired += 1
            return {
                "tool": name,
                "error_class": cls,
                "streak": self._streak,
                "nudge": nudge_text(name, cls, self._streak, self._last_output),
                "output": self._last_output,
            }
        return None

    @property
    def current_pair(self) -> tuple[str, str] | None:
        return self._pair

    @property
    def current_streak(self) -> int:
        return self._streak

    def record_reset(self) -> None:
        """Re-arm after a fired signal: the next identical failure counts a
        fresh streak (so a persistent blocker re-fires every STREAK_THRESHOLD
        failures instead of going silent forever)."""
        self._pair = None
        self._streak = 0


def enabled() -> bool:
    """Kill switch: CODEMONKEY_STUCK=0 disables the stuck signal."""
    return os.environ.get("CODEMONKEY_STUCK", "1") != "0"
