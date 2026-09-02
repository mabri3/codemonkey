"""read_file — file contents with line numbers and pagination."""

from __future__ import annotations
from .base import ToolResult, _err, _load


def run(args: dict, ctx) -> ToolResult:
    try:
        path = args["path"]
        offset = int(args.get("offset", 1))
        limit = int(args.get("limit", 2000))
        raw = _load(path, ctx)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        total = len(lines)
        start = max(offset, 1)
        if start > total:
            return ToolResult(output=f"line {start} out of range (file has {total} lines)", ok=False)
        end = min(start + limit - 1, total)
        body = "\n".join(f"{i:6d}| {lines[i-1]}" for i in range(start, end + 1))
        footer = f"\n[total_lines={total}]"
        return ToolResult(output=body + footer)
    except Exception as e:
        return _err(e)
