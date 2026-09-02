"""edit_file — targeted old_string -> new_string replacement.

Rejection rules (spec): old_string missing, or matching in more than one
place without `replace_all`, is an error — the LLM must add context or set
replace_all. Empty old_string is an error (use write_file instead).
"""

from __future__ import annotations
from .base import ToolResult, _err, _load, _save


def run(args: dict, ctx) -> ToolResult:
    try:
        path = args["path"]
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        replace_all = bool(args.get("replace_all", False))
        if not old:
            return ToolResult(output="error: old_string must be non-empty (use write_file to create files)", ok=False)
        raw = _load(path, ctx)
        text = raw.decode("utf-8", errors="replace")
        count = text.count(old)
        if count == 0:
            return ToolResult(output=f"error: old_string not found in {path} (check whitespace/indent)", ok=False)
        if count > 1 and not replace_all:
            return ToolResult(
                output=f"error: old_string matches {count} places; add context to make it unique or set replace_all=true",
                ok=False,
            )
        if replace_all:
            replaced = text.replace(old, new)
            n = count
        else:
            replaced = text.replace(old, new, 1)
            n = 1
        _save(path, replaced, ctx)
        return ToolResult(output=f"replaced {n} occurrence(s) in {path}")
    except Exception as e:
        return _err(e)
