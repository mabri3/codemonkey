"""repo_map tool (loop4, cycle 20): read-only symbol index of the repo."""

from __future__ import annotations

from .base import ToolResult, _err


def run(args: dict, ctx) -> ToolResult:
    try:
        from .. import repomap as rm_mod

        path = args.get("path", ".")
        pattern = args.get("pattern") or None
        limit = int(args.get("limit", 200) or 200)
        from ..sandbox import validate_root

        root = validate_root(ctx, path)
        repo_map = rm_mod.scan_repo(root)
        text = rm_mod.format_map(repo_map, pattern=pattern, limit=limit)
        n_files = len([k for k in repo_map if (pattern is None or True)])
        return ToolResult(output=text or "(empty repo map)")
    except Exception as e:
        return _err(e)
