"""Dry-run previews (loop22, cycle 59).

exec --dry-run: mutating tool calls return a PREVIEW payload instead of
executing — the model sees "DRY-RUN (not executed)" and can revise; the
journal records type=preview for the audit trail. Read-only tools run
normally.
"""

from __future__ import annotations


def preview_for(name: str, args: dict) -> str:
    """Human/model-readable preview of what WOULD execute."""
    if name == "write_file":
        content = str(args.get("content", ""))
        first = content.splitlines()[:3]
        head = " | ".join(first)
        return (f"DRY-RUN (not executed): write_file {args.get('path')} "
                f"({len(content)} bytes): {head[:120]}")
    if name == "edit_file":
        search = str(args.get("old_string") or args.get("search") or "")
        replace = str(args.get("new_string") or args.get("replace") or "")
        return (f"DRY-RUN (not executed): edit_file {args.get('path')} — "
                f"search {len(search)} chars -> replace {len(replace)} chars")
    if name == "shell":
        return f"DRY-RUN (not executed): shell $ {str(args.get('command', ''))[:120]}"
    if name in ("delegate", "delegate_batch"):
        return (f"DRY-RUN (not executed): {name} — "
                f"{str(args.get('task', args.get('tasks', '')))[:100]}")
    return f"DRY-RUN (not executed): {name}"


MUTATING = {"write_file", "edit_file", "shell", "delegate", "delegate_batch"}
