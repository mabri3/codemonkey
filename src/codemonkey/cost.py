"""Token/cost telemetry (loop5, cycle 26).

Per-run usage aggregation + a cumulative ledger at
~/.codemonkey/cost.json. Sources: turn.completed usage events already
flowing through the loop; per-tool-call counts from tool.started events.

Summary dict shape (cost_summary):
  {turns, total_tokens, prompt_tokens, completion_tokens,
   tool_calls: {name: count}, wall_seconds}
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


def ledger_path() -> Path:
    d = Path.home() / ".codemonkey"
    d.mkdir(parents=True, exist_ok=True)
    return d / "cost.json"


def summarize(events: list, *, wall_seconds: float = 0.0) -> dict:
    """Aggregate a JSONL event list (list of dicts) into a cost summary."""
    s = {
        "turns": 0,
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "tool_calls": {},
        "wall_seconds": round(wall_seconds, 2),
    }
    for ev in events:
        et = ev.get("type")
        if et == "turn.started":
            s["turns"] += 1
        elif et == "turn.completed":
            u = ev.get("usage") or {}
            s["total_tokens"] += int(u.get("total_tokens") or 0)
            s["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
            s["completion_tokens"] += int(u.get("completion_tokens") or 0)
        elif et == "tool.started":
            name = ev.get("name") or "?"
            s["tool_calls"][name] = s["tool_calls"].get(name, 0) + 1
    return s


def append_to_ledger(summary: dict, *, suite: str = "", thread_id: str = "",
                     path: Optional[Path] = None) -> dict:
    """Append a run's summary to the cumulative ledger; returns the ledger."""
    p = path or ledger_path()
    try:
        ledger = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        ledger = {"runs": [], "total_tokens": 0, "total_turns": 0}
    ledger.setdefault("runs", []).append({
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "suite": suite,
        "thread_id": thread_id,
        **{k: v for k, v in summary.items()},
    })
    ledger["total_tokens"] = ledger.get("total_tokens", 0) + summary.get("total_tokens", 0)
    ledger["total_turns"] = ledger.get("total_turns", 0) + summary.get("turns", 0)
    p.write_text(json.dumps(ledger, indent=2))
    return ledger


def render_summary(summary: dict) -> str:
    """Human one-block rendering for --cost-summary."""
    lines = [
        f"turns: {summary.get('turns', 0)}",
        f"tokens: {summary.get('total_tokens', 0)} "
        f"(prompt {summary.get('prompt_tokens', 0)}, "
        f"completion {summary.get('completion_tokens', 0)})",
        f"wall: {summary.get('wall_seconds', 0)}s",
    ]
    tools = summary.get("tool_calls") or {}
    if tools:
        calls = ", ".join(f"{k} x{v}" for k, v in sorted(tools.items()))
        lines.append(f"tool calls: {calls}")
    else:
        lines.append("tool calls: none")
    return "\n".join(lines)
