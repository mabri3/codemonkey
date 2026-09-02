"""glob — find files by pattern, mtime-descending (rg --files -g style)."""

from __future__ import annotations
from pathlib import Path
from .base import ToolResult, _err
from ..sandbox import validate_root


def run(args: dict, ctx) -> ToolResult:
    try:
        pattern = args["pattern"]
        rp = validate_root(ctx, args.get("path", "."))
        hits = [p for p in rp.rglob("*") if Path(p.name).match(pattern) or p.match(pattern)]
        # also allow glob segments like src/*.py
        hits = list({h for h in hits} | {p for p in rp.glob(pattern)})
        hits = sorted(hits, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
        limit = int(args.get("limit", 100))
        lines = [str(h) for h in hits[:limit]]
        if not lines:
            return ToolResult(output=f"no files matching {pattern!r}")
        return ToolResult(output="\n".join(lines))
    except Exception as e:
        return _err(e)
