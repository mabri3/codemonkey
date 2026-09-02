"""JSONL event emitters (codex-style contract, spec §JSONL).

stdout purity rule (exec.py):
  text mode : ONLY the final response on stdout; these helpers write to stderr.
  json mode : ONLY these events on stdout; everything human (deltas, tool
              notices, errors) goes to stderr.

Item types: agent_message | reasoning | command_execution | file_change | plan
Line types: thread.started, thread.item.started, thread.item.completed,
            turn.started, turn.completed, error
(We emit codex-compatible `"thread.item.*"` type strings while also keeping
thread.started / turn.started / turn.completed / error which plan.md names.)
"""

from __future__ import annotations

import json
import sys
import uuid


def new_thread_id() -> str:
    return uuid.uuid4().hex[:12]


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
        if etype == "error":
            print(f"error: {event.get('message')}", file=sink, flush=True)
            return
        if etype == "thread.item.started":
            item = event.get("item", {})
            itype, tool = item.get("type", ""), item.get("tool", "")
            if itype == "command_execution":
                print(f"$ {item.get('command', '')}", file=sink, flush=True)
            elif itype == "file_change":
                print(f"[edit] {item.get('path', '')} ({tool})", file=sink, flush=True)
            elif itype == "reasoning":
                print("[reasoning…]", file=sink, flush=True)
            return
        if etype == "thread.item.completed":
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


def item_start_sink(
    thread_id: str, *, json_mode: bool, stream=None
):
    """Return an on_event callback that maps loop.run_turns events to items.

    run_turns emits: turn.started, tool.started{name}, tool.completed{name,ok},
    turn.completed{usage}, notice{message}, error{message}.
    Items are synthesized per tool call: read-ish tools don't echo fully here —
    exec.py keeps its own dispatch wrapper for exact item payloads, so this
    sink only translates turn-level + error + notice events.
    """
    state = {"open": {}}

    def sink(ev: dict) -> None:
        etype = ev.get("type", "")
        if etype == "turn.started":
            emit({"type": "turn.started"}, json_mode=json_mode, stream=stream)
        elif etype == "turn.completed":
            emit(
                {"type": "turn.completed", "usage": ev.get("usage") or {}},
                json_mode=json_mode,
                stream=stream,
            )
        elif etype == "notice":
            emit(
                {"type": "notice", "message": ev.get("message", "")},
                json_mode=json_mode,
                stream=stream,
            )
        elif etype == "error":
            emit(
                {"type": "error", "message": ev.get("message", "")},
                json_mode=json_mode,
                stream=stream,
            )

    return sink
