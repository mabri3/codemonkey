"""update_plan — replace or append a plan item (pure state, no files).

Plan state lives in ctx.extra['plan'] (list of {id, content, status}) and is
serialized by the agent loop between turns so the model's plan survives.
"""

from __future__ import annotations
from .base import ToolResult, _err


def _plan(ctx) -> list:
    if "plan" not in ctx.extra:
        ctx.extra["plan"] = []
    return ctx.extra["plan"]


def _render(items: list) -> str:
    if not items:
        return "(empty plan)"
    return "\n".join(
        f"{i + 1}. [{it.get('status', 'pending')}] {it['content']}" for i, it in enumerate(items)
    )


def run(args: dict, ctx) -> ToolResult:
    try:
        mode = args.get("mode", "append")
        items = _plan(ctx)
        if mode == "clear":
            items.clear()
            return ToolResult(output=_render(items))
        item = {
            "id": args.get("id", f"p{len(items) + 1}"),
            "content": args.get("content", "").strip(),
            "status": args.get("status", "pending"),
        }
        if not item["content"]:
            return ToolResult(output="error: content required", ok=False)
        if mode == "replace":
            # same id replaces, else append
            for i, it in enumerate(items):
                if it["id"] == item["id"]:
                    items[i] = item
                    break
            else:
                items.append(item)
        elif mode == "append":
            items.append(item)
        else:
            return ToolResult(output=f"error: unknown mode {mode!r}", ok=False)
        return ToolResult(output=_render(items))
    except Exception as e:
        return _err(e)
