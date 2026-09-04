"""Loop 26 (cycle 63): verify-gate auto-suggestion."""

from __future__ import annotations

from codemonkey.verifyhint import suggest_verify_command


SHELL_PYTEST = [{"tool": "shell", "output": "pytest test_x.py: 3 passed"}]
SHELL_NO_TEST = [{"tool": "shell", "output": "ls -la"}]


def test_suggestion_when_pytest_used():
    s = suggest_verify_command(SHELL_PYTEST, configured=None)
    assert s and "verify_command" in s and "pytest" in s


def test_no_suggestion_without_pytest():
    assert suggest_verify_command(SHELL_NO_TEST, configured=None) is None


def test_silent_when_configured():
    assert suggest_verify_command(SHELL_PYTEST, configured="python -m pytest -q") is None


def test_suggestion_object_stable():
    """The suggestion is deterministic — same inputs, same text."""
    s1 = suggest_verify_command(SHELL_PYTEST, configured=None)
    s2 = suggest_verify_command(SHELL_PYTEST, configured=None)
    assert s1 == s2
