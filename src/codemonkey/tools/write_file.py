"""write_file — create or overwrite a file (sandbox-gated)."""

from __future__ import annotations
from .base import ToolResult, _err, _save


def run(args: dict, ctx) -> ToolResult:
    try:
        rp = _save(args["path"], args.get("content", ""), ctx)
        n = len(args.get("content", ""))
        return ToolResult(output=f"wrote {n} bytes to {rp}")
    except Exception as e:
        return _err(e)
