"""update_memory tool (7F1): append a durable fact to the memory store."""

from __future__ import annotations

from .base import ToolResult, _err


def run(args: dict, ctx) -> ToolResult:
    try:
        fact = str(args.get("fact") or args.get("content") or "").strip()
        if not fact:
            return ToolResult(output="error: fact must be non-empty", ok=False)
        # memory instance is attached to the ctx by exec/repl when enabled
        mem = getattr(ctx, "extra", {}).get("memory") if hasattr(ctx, "extra") else None
        if mem is None:
            return ToolResult(
                output="error: memory is disabled (strategies.memory = none)",
                ok=False,
            )
        before = mem.load()
        mem.add_fact(fact)
        after = mem.load()
        if fact in before:
            return ToolResult(output="memory unchanged (fact already present)")
        return ToolResult(output="memory updated")
    except Exception as e:
        return _err(e)
