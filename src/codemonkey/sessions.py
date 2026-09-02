"""Session persistence + resume (cycle 6 avatar; cycle 7 swaps the backend
into the strategies/session_state.py registry).

Layout: ~/.codemonkey/sessions/<thread_id>.jsonl — one JSON event per line,
append-only:

  {"type": "meta", "thread_id", "provider", "model", "cwd", "created", "updated"}
  {"type": "message", "role": "user"|"assistant", "content": "..."}

`resume` loads the message list back into the conversation. `--ephemeral`
skips persistence entirely.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


def sessions_dir() -> Path:
    d = Path.home() / ".codemonkey" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(thread_id: str) -> Path:
    return sessions_dir() / f"{thread_id}.jsonl"


class SessionStore:
    """Append-only jsonl session store (default backend)."""

    name = "jsonl"

    def append_meta(self, thread_id: str, *, provider: str, model: str, cwd: str) -> None:
        self._append(thread_id, {
            "type": "meta",
            "thread_id": thread_id,
            "provider": provider,
            "model": model,
            "cwd": cwd,
            # `created` is a FLOOR: on the first append_meta for a brand-new
            # thread it stamps now(), but every later meta append (post-loop
            # refresh, resume run) reuses the earliest recorded `created` so
            # the field never drifts across the thread's life (cycle 6F4).
            "created": self._prior_created(thread_id) or time.time(),
            "updated": time.time(),
        })

    @staticmethod
    def _prior_created(thread_id: str) -> Optional[float]:
        """Earliest `created` from any existing meta event for this thread.

        First-write returns None (fresh thread); subsequent appends reuse the
        floor so `created` is stamped exactly once per thread.
        """
        p = _path(thread_id)
        if not p.exists():
            return None
        try:
            for line in p.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "meta" and isinstance(ev.get("created"), (int, float)):
                    return ev["created"]
        except OSError:
            return None
        return None

    def append_message(self, thread_id: str, role: str, content: str) -> None:
        self._append(thread_id, {"type": "message", "role": role, "content": content, "ts": time.time()})

    def _append(self, thread_id: str, event: dict) -> None:
        event.setdefault("ts", time.time())
        with _path(thread_id).open("a") as fh:
            fh.write(json.dumps(event) + "\n")

    def load(self, thread_id: str) -> dict:
        """Returns {meta: {...}, messages: [...]}. Raises FileNotFoundError."""
        p = _path(thread_id)
        if not p.exists():
            raise FileNotFoundError(f"no persisted session for thread {thread_id}")
        meta: dict = {}
        messages: list[dict] = []
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "meta":
                meta = ev
            elif ev.get("type") == "message":
                messages.append({"role": ev["role"], "content": ev["content"]})
        # de-dup meta appends: keep the last-seen meta as authoritative
        return {"meta": meta, "messages": messages}

    def list(self) -> list[dict]:
        out = []
        for p in sorted(sessions_dir().glob("*.jsonl"), key=lambda q: q.stat().st_mtime, reverse=True):
            try:
                data = self.load(p.stem)
            except FileNotFoundError:
                continue
            meta = data["meta"]
            first_user = next(
                (m["content"] for m in data["messages"] if m["role"] == "user"), ""
            )
            out.append({
                "thread_id": p.stem,
                "provider": meta.get("provider", "?"),
                "model": meta.get("model", "?"),
                "created": meta.get("created") or p.stat().st_mtime,
                "updated": meta.get("updated") or p.stat().st_mtime,
                "n_messages": len(data["messages"]),
                "first_prompt": first_user[:80],
                "cwd": meta.get("cwd", ""),
            })
        return out

    def latest(self) -> Optional[str]:
        items = self.list()
        return items[0]["thread_id"] if items else None


def get_store(cfg: dict) -> SessionStore:
    """Cycle 6: always the jsonl store; cycle 7 routes via the strategies
    registry (kept behind this seam)."""
    return SessionStore()


# Cycle-6 default singleton. `store(cfg)` is THE accessor run_exec uses;
# tests (and later the strategies registry) can shadow `store` on the module
# to substitute a tmp-dir or alternate-backend store without monkeypatching
# races.
_DEFAULT_STORE = SessionStore()


def store(cfg: Optional[dict] = None) -> SessionStore:  # noqa: D103
    return get_store(cfg or {})
