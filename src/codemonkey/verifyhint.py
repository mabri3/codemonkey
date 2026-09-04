"""verify-gate auto-suggestion (loop26, cycle 63).

If the run exercised pytest and no verify_command is configured, suggest the
gate (one notice + session meta). Never auto-enables: the suggestion keeps
the operator in charge (loop-16 governance precedent).
"""

from __future__ import annotations


def suggest_verify_command(tool_records: list[dict],
                           configured: str | None) -> str | None:
    """Return the suggestion text, or None (used already / not applicable)."""
    if configured:
        return None
    used_pytest = any(
        r.get("tool") == "shell" and "pytest" in str(r.get("output", ""))
        for r in tool_records)
    if not used_pytest:
        return None
    return ("verify gate available: add verify_command: \"python -m pytest -q\" "
            "to auto-check fixes")
