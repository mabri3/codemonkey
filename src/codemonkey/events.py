"""JSONL event emitters (codex-style contract, spec §JSONL).

stdout purity rule (exec.py):
  text mode : ONLY the final response on stdout; these helpers write to stderr.
  json mode : ONLY these events on stdout; everything human (deltas, tool
              notices, errors) goes to stderr.

Item types: agent_message | reasoning | command_execution | file_change | plan
Line types (spec §JSONL contract): thread.started{thread_id},
            turn.started, item.started, item.completed,
            turn.completed{usage}, error{message}
"""

from __future__ import annotations

import json
import sys
import uuid


def new_thread_id() -> str:
    return uuid.uuid4().hex[:12]


# loop43 cycle 101: versioned event envelope. Every event crossing the exec
# boundary carries v=SCHEMA_V. Additive minor versions add fields; breaking
# changes bump major. stamp() setdefaults — never clobbers an explicit v.
SCHEMA_V = 1


def stamp(event: dict) -> dict:
    event.setdefault("v", SCHEMA_V)
    return event


def emit(event: dict, *, json_mode: bool, stream=None) -> None:
    """Write one event: JSONL line on stdout in json mode, human line to
    stderr otherwise. Never errors — event emission must not crash a run."""
    if json_mode:
        try:
            print(json.dumps(event, ensure_ascii=False), flush=True)
        except Exception:  # pragma: no cover - stdout must keep flowing
            pass
        return
    sink = stream or sys.stderr
    try:
        etype = event.get("type", "")
        if etype in ("thread.started", "turn.started"):
            return  # silent in text mode
        if etype == "turn.completed":
            usage = event.get("usage") or {}
            pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
            if pt is not None or ct is not None:
                print(f"[usage] prompt={pt} completion={ct}", file=sink, flush=True)
            return
        if etype == "stuck":
            print(f"[stuck] {event.get('tool')} failed "
                  f"{event.get('streak')}x in a row "
                  f"({event.get('error_class')}) — nudge appended",
                  file=sink, flush=True)
            return
        if etype == "error":
            print(f"error: {event.get('message')}", file=sink, flush=True)
            return
        if etype == "item.started":
            item = event.get("item", {})
            itype, tool = item.get("type", ""), item.get("tool", "")
            if itype == "command_execution":
                print(f"$ {item.get('command', '')}", file=sink, flush=True)
            elif itype == "file_change":
                print(f"[edit] {item.get('path', '')} ({tool})", file=sink, flush=True)
            elif itype == "reasoning":
                print("[reasoning…]", file=sink, flush=True)
            return
        if etype == "item.completed":
            item = event.get("item", {})
            itype = item.get("type", "")
            if itype == "agent_message":
                preview = (item.get("text") or "").replace("\n", " ")[:80]
                print(f"[agent] {preview}", file=sink, flush=True)
            elif itype == "command_execution":
                print(
                    f"[exit {item.get('exit_code')}] "
                    + (item.get("aggregated_output") or "")[:400],
                    file=sink, flush=True,
                )
            elif itype == "plan":
                print(f"[plan] {(item.get('text') or '')[:300]}", file=sink, flush=True)
            return
        if etype == "notice":
            print(f"[notice] {event.get('message')}", file=sink, flush=True)
    except Exception:  # pragma: no cover
        pass


# 102F3 (R-A, measure-or-delete): `item_start_sink` lived here from loop 12
# to loop 43 with zero callers in src/, tests/ or docs — and it emitted via
# `events.emit` directly, bypassing both exec funnels, so wiring it up would
# have put UNSTAMPED events on stdout in --json mode and broken contract §2
# silently. exec.py's own dispatch wrapper builds the item stream. Deleted.
