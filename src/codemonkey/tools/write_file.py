"""write_file — create or overwrite a file (sandbox-gated)."""

from __future__ import annotations
from .base import ToolResult, _err, _save

try:
    from ..grounding import pre_apply_validate
except ImportError:  # pragma: no cover (flat import during early init)
    pre_apply_validate = None


def run(args: dict, ctx) -> ToolResult:
    content = args.get("content", "")
    # loop R29: pre-apply validation — a .py/.json write never lands with a
    # syntax error (opt-out via strict_precheck=false config, default ON).
    if pre_apply_validate is not None and getattr(
            ctx, "strict_precheck", True):
        err = pre_apply_validate(args.get("path", ""), content)
        if err:
            return ToolResult(output=f"error: pre-apply check failed: {err}",
                              ok=False)
    try:
        rp = _save(args["path"], content, ctx)
        n = len(content)
        return ToolResult(output=f"wrote {n} bytes to {rp}")
    except Exception as e:
        return _err(e)
