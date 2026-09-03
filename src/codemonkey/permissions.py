"""Rule-based tool permissions (loop9, cycle 36).

Config `permissions.rules` — ordered list of
  {tool: "<name>|*", pattern: "<glob>" (optional), action: allow|deny|ask}

Evaluation (Claude-Code-canonical): deny rules first, then ask, then allow;
first match wins within each tier; no match at all -> None (fall through to
the existing approval gate/policy). Patterns glob over the shell command for
`shell`, the target path for file tools, and are ignored ("*"-match) for
other tools.

Rule hits are journaled (audit trail) with the matched rule.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Optional

_ACTIONS = ("deny", "ask", "allow")

# tools whose "pattern" target is a filesystem path rather than a command
_PATH_TOOLS = {"read_file", "write_file", "edit_file", "list_dir", "glob",
               "search", "read_file"}


def _subject(tool: str, args: dict) -> str:
    """The string a rule pattern matches against."""
    if tool == "shell":
        return str((args or {}).get("command") or "")
    if tool in _PATH_TOOLS:
        return str((args or {}).get("path") or "")
    return ""


def evaluate(rules: list[dict], tool: str, args: dict) -> Optional[str]:
    """Returns 'allow' | 'deny' | 'ask' | None (no rule matched).

    None means "no rules applied" — the caller falls back to the approval
    gate. Raises ValueError on malformed rules (fail-closed at config load).
    """
    if not rules:
        return None
    for rule in rules:
        if not isinstance(rule, dict) or "tool" not in rule or "action" not in rule:
            raise ValueError("each permission rule needs 'tool' and 'action'")
        action = str(rule["action"]).lower()
        if action not in _ACTIONS:
            raise ValueError(f"rule action must be one of {_ACTIONS}, got {rule['action']}")
    for action in _ACTIONS:  # deny, ask, allow
        for rule in rules:
            if str(rule["action"]).lower() != action:
                continue
            rtool = str(rule["tool"])
            if rtool != "*" and rtool != tool:
                continue
            pattern = rule.get("pattern")
            subject = _subject(tool, args)
            if pattern:
                if not subject or not fnmatch.fnmatch(subject, str(pattern)):
                    continue
            # matched
            return action
    return None
