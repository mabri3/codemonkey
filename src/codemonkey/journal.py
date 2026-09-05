"""Execution journal (loop7, cycle 31).

Append-only per-thread journal at ~/.codemonkey/journal/<thread>.jsonl:
  {"ts": ..., "type": "intent"|"outcome", "thread": ..., "tool": ...,
   "key": <idempotency hash>, "error_class": ..., "duration_ms": ...}

Raw tool arguments are NEVER stored — only a stable hash of them. The journal
is the audit trail for "what was the agent about to do when it died" and the
replay source for idempotent mutating tools (cycle 32).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

ERROR_CLASSES = ("transport", "auth", "timeout", "parse", "tool-error",
                 "budget", "unknown")


def journal_dir() -> Path:
    d = Path.home() / ".codemonkey" / "journal"
    d.mkdir(parents=True, exist_ok=True)
    return d


def journal_path(thread_id: str) -> Path:
    return journal_dir() / f"{thread_id}.jsonl"


def args_key(thread_id: str, turn: int, call_index: int, args: dict,
             run: str = "") -> str:
    """Stable idempotency key: thread+run+turn+call-index+canonical args hash.

    `run` scopes the key to ONE invocation (31F1). Cycle 32's replay exists to
    de-duplicate a retry inside a run; without a run scope a resumed thread
    restarts turn numbering at 1 and would replay the previous invocation's
    "wrote N bytes" outcome without writing anything. Callers that want the
    pre-31F1 cross-call behavior (the in-process recovery tests) omit `run`.
    """
    payload = json.dumps(args, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256(
        f"{thread_id}|{run}|{turn}|{call_index}|{payload}".encode()
    ).hexdigest()
    return h[:24]


def classify_error(exc: BaseException | None) -> str:
    """Map an exception to the fixed error-class enum."""
    if exc is None:
        return "unknown"
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    if "auth" in name or "401" in text or "403" in text:
        return "auth"
    if "timeout" in name or "timeout" in text or "deadline" in text:
        return "timeout"
    if "transport" in name or "connect" in text or "stream wall-clock" in text:
        return "transport"
    if "json" in name or "parse" in name or "parse" in text:
        return "parse"
    from .providers.base import ProviderError
    if isinstance(exc, ProviderError):
        return "tool-error"
    return "unknown"


def record(thread_id: str, record_type: str, *, tool: str, key: str,
           status: str = "", error_class: str = "", duration_ms: int = 0,
           output: str = "", cmd: str = "") -> dict:
    """Append one journal record. Best-effort: never raises into the loop.

    `cmd` (96F1) carries a shell command ALREADY redacted by the caller via
    `redact.redact_text` — record() never sees the raw command. Capped at
    500 chars; empty means "not a shell call" (or "needles unknown").
    """
    rec = {
        "ts": time.time(),
        "type": record_type,
        "thread": thread_id,
        "tool": tool,
        "key": key,
    }
    if status:
        rec["status"] = status
    if error_class:
        rec["error_class"] = error_class
    if duration_ms:
        rec["duration_ms"] = duration_ms
    if output:
        rec["output"] = output[:2000]  # replay payload cap (cycle 32)
    if cmd:
        rec["cmd"] = cmd[:500]  # 96F1: pre-redacted shell text, hard cap
    try:
        with journal_path(thread_id).open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    return rec


def find_outcome(thread_id: str, key: str) -> Optional[dict]:
    """The most recent outcome record for a key (replay source for cycle 32)."""
    p = journal_path(thread_id)
    try:
        found = None
        for line in p.read_text().splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "outcome" and ev.get("key") == key:
                found = ev
        return found
    except OSError:
        return None


def read_thread(thread_id: str) -> list[dict]:
    p = journal_path(thread_id)
    try:
        out = []
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
    except OSError:
        return []


def list_threads() -> list[str]:
    return sorted(p.stem for p in journal_dir().glob("*.jsonl"))


def class_summary(records: list[dict]) -> dict[str, int]:
    """Counts of error_class across outcome records."""
    counts: dict[str, int] = {}
    for rec in records:
        if rec.get("type") == "outcome":
            cls = rec.get("error_class") or "ok"
            counts[cls] = counts.get(cls, 0) + 1
    return counts
