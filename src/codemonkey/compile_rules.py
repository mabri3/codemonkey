"""Corrections compiled into enforcement (R34).

Recurring journal failures of the same (tool, error_class) compile into
DRAFT permission rules (`{"tool", "pattern", "action": "ask"}`) so repeated
mistakes get a gate next run — enforcement, generated from evidence.
Drafts stay drafts until the operator saves them into config (governance).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

_THRESHOLD = 2


def compile_corrections(journal_classes: dict[tuple[str, str], int],
                        *, threshold: int = _THRESHOLD,
                        existing_rules: list | None = None) -> list[dict]:
    """(tool, error_class) over threshold → 'ask' rules. Skips tools already
    covered by an existing deny/ask rule for that tool."""
    covered = {r.get("tool") for r in (existing_rules or [])
               if r.get("action") in ("deny", "ask") and r.get("tool") != "*"}
    out = []
    for (tool, eclass), n in sorted(journal_classes.items(),
                                    key=lambda kv: (-kv[1], kv[0])):
        if n < threshold or tool in ("*", "route", "verify_claims", "failover"):
            continue
        if tool in covered:
            continue
        if eclass in ("schema_mismatch", "timeout", "tool_error"):
            out.append({"tool": tool, "pattern": "*", "action": "ask",
                        "reason": f"recurring {eclass} failures (n={n})"})
    return out


def merge_rules(current: list, drafts: list) -> list:
    """Append drafts that aren't duplicates of current rules."""
    seen = {(r.get("tool"), r.get("pattern")) for r in (current or [])}
    out = list(current or [])
    added = []
    for d in drafts:
        k = (d["tool"], d["pattern"])
        if k not in seen:
            out.append(d)
            seen.add(k)
            added.append(d)
    return out
