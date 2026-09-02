"""list_dir — directory listing, most-recently-modified first."""

from __future__ import annotations
from .base import ToolResult, _err
from ..sandbox import validate_root
from pathlib import Path


def run(args: dict, ctx) -> ToolResult:
    try:
        rp = validate_root(ctx, args.get("path", "."))
        entries = sorted(
            rp.iterdir(),
            key=lambda p: (not p.is_dir(), p.stat().st_mtime, p.name),
        )
        lines = []
        for p in entries[:500]:
            kind = "dir" if p.is_dir() else "file"
            size = "" if p.is_dir() else f" {p.stat().st_size}B"
            lines.append(f"{kind} {p.name}{size}")
        if not lines:
            return ToolResult(output=f"{rp} (empty)")
        return ToolResult(output="\n".join(lines[:200]))
    except Exception as e:
        return _err(e)
