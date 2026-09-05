"""Reproduction-test-first gate (loop 40, cycle 93).

For fix runs with the verify gate active: a patch counts as verified ONLY if
the run observed the failure BEFORE the patch (write-test → run-expect-FAIL
→ allow-patch → run-expect-PASS). Pass-only runs are UNVERIFIED — a test
that never failed proves nothing.

Tracked only when a verify command is configured; otherwise the tracker is
never instantiated and behavior is unchanged. Pure state machine, no I/O.
"""

from __future__ import annotations


def is_test_path(path: str) -> bool:
    """Test file by convention: test_*.py / *_test.py, or under tests/."""
    parts = str(path or "").replace("\\", "/").split("/")
    base = parts[-1] if parts else ""
    if base.startswith("test_") or base.endswith("_test.py"):
        return True
    return any(p in ("tests", "test") for p in parts[:-1])


class ReproTracker:
    """Fail-first state machine over one run's writes + verify outcomes."""

    def __init__(self):
        self.test_written = False
        self.fail_observed = False
        self.patched = False
        self.pass_observed = False
        self.transitions: list[str] = []

    def note_write(self, path: str) -> None:
        """A successful file write. Test writes (re)open a cycle; any other
        write after an observed failure is the patch under test."""
        if is_test_path(path):
            # a fresh repro restarts the cycle (old evidence belongs to it)
            self.test_written = True
            self.fail_observed = False
            self.patched = False
            self.pass_observed = False
            self.transitions.append(f"test-written:{path}")
        elif self.fail_observed and not self.pass_observed:
            self.patched = True
            self.transitions.append(f"patched:{path}")

    def note_verify(self, ok: bool) -> None:
        """A verify-gate outcome. A failure only counts as the repro failing
        if the test was written first; a pass only counts post-patch."""
        if not ok and self.test_written and not self.pass_observed:
            self.fail_observed = True
            self.transitions.append("fail-observed")
        elif ok and self.fail_observed and self.patched:
            self.pass_observed = True
            self.transitions.append("pass-observed")

    def verdict(self) -> str:
        if self.fail_observed and self.patched and self.pass_observed:
            return "VERIFIED"
        return "UNVERIFIED"

    def reason(self) -> str:
        if not self.test_written:
            return "no reproduction test was written"
        if not self.fail_observed:
            return "the failure was never observed (verify never failed post-test)"
        if not self.patched:
            return "no patch followed the observed failure"
        return "no passing verify observed after the patch"

    def report(self) -> dict:
        v = self.verdict()
        return {
            "type": "repro.verdict",
            "verdict": v,
            "test_written": self.test_written,
            "fail_observed": self.fail_observed,
            "patched": self.patched,
            "pass_observed": self.pass_observed,
            "reason": "" if v == "VERIFIED" else self.reason(),
            "transitions": list(self.transitions),
        }
