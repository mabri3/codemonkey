"""Session-state strategies (cycle 7): pluggable backends, config-selected.

Protocol (SessionStore):
    append_meta(thread_id, *, provider, model, cwd)
    append_message(thread_id, role, content)
    load(thread_id) -> dict {"messages": [{"role","content"}, ...]}
    list() -> list[dict]   # one entry per thread: thread_id, created, updated
    latest() -> str | None # most recently updated thread id

Backends:
  - jsonl (default): ~/.codemonkey/sessions/<thread_id>.jsonl, one JSON
    event per line. Reuses the cycle-6 store implementation.
  - sqlite: ~/.codemonkey/sessions.db — one row per event, same semantics.

Both backends persist identical event shapes so `resume` works unchanged
regardless of backend.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


def sessions_dir() -> Path:
    d = Path.home() / ".codemonkey" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(thread_id: str) -> Path:
    return sessions_dir() / f"{thread_id}.jsonl"


class JsonlStore:
    """Append-only JSONL session store (default backend)."""

    name = "jsonl"

    def __init__(self, base: Path | None = None):
        self.base = base or sessions_dir()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, thread_id: str) -> Path:
        return self.base / f"{thread_id}.jsonl"

    def append_meta(self, thread_id: str, *, provider: str, model: str, cwd: str) -> None:
        created = self._prior_created(thread_id) or time.time()
        self._append(thread_id, {
            "type": "meta",
            "thread_id": thread_id,
            "provider": provider,
            "model": model,
            "cwd": cwd,
            # `created` is a FLOOR: stamped once on first write, later meta
            # appends (resume refresh, post-loop persist) reuse the original
            # so the field never drifts across the thread's life.
            "created": created,
            "updated": time.time(),
        })

    def _prior_created(self, thread_id: str) -> Optional[float]:
        p = self._path(thread_id)
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
        with self._path(thread_id).open("a") as f:
            f.write(json.dumps(event) + "\n")

    def load(self, thread_id: str) -> dict:
        p = self._path(thread_id)
        if not p.exists():
            raise FileNotFoundError(f"no such thread: {thread_id}")
        messages = []
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "message":
                messages.append({"role": ev.get("role"), "content": ev.get("content", "")})
        return {"messages": messages}

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.base.glob("*.jsonl"), key=lambda q: q.stat().st_mtime, reverse=True):
            try:
                data = self.load(p.stem)
            except FileNotFoundError:
                continue
            meta, messages = None, data["messages"]
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
                    break   # earliest meta (file is append-ordered)
            first_user = next(
                (m.get("content", "") for m in messages if m.get("role") == "user"), ""
            )
            out.append({
                "thread_id": p.stem,
                "provider": (meta or {}).get("provider", "?"),
                "model": (meta or {}).get("model", "?"),
                "created": (meta or {}).get("created") or p.stat().st_mtime,
                "updated": (meta or {}).get("updated") or p.stat().st_mtime,
                "n_messages": len(messages),
                "first_prompt": first_user[:80],
                "cwd": (meta or {}).get("cwd", ""),
            })
        return out

    def latest(self) -> Optional[str]:
        entries = self.list()
        return entries[-1]["thread_id"] if entries else None

    # protocol aliases: generic `append` routes by event type
    def append(self, thread_id: str, event: dict) -> None:
        if event.get("type") == "meta":
            self.append_meta(
                thread_id,
                provider=event.get("provider", ""),
                model=event.get("model", ""),
                cwd=event.get("cwd", ""),
            )
        elif event.get("type") == "message":
            self.append_message(thread_id, event.get("role", ""), event.get("content", ""))


class SqliteStore:
    """SQLite session store: one row per event, same semantics as jsonl."""

    name = "sqlite"

    def __init__(self, path: Path | None = None):
        self.path = path or (Path.home() / ".codemonkey" / "sessions.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "thread_id TEXT NOT NULL, type TEXT NOT NULL, "
                "payload TEXT NOT NULL, ts REAL NOT NULL, PRIMARY KEY (thread_id, ts, payload))"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.path))

    def append_meta(self, thread_id: str, *, provider: str, model: str, cwd: str) -> None:
        created = self._prior_created(thread_id) or time.time()
        self._append(thread_id, {
            "type": "meta",
            "thread_id": thread_id,
            "provider": provider,
            "model": model,
            "cwd": cwd,
            "created": created,
            "updated": time.time(),
        })

    def _prior_created(self, thread_id: str) -> Optional[float]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload FROM events WHERE thread_id=? AND type='meta' "
                "ORDER BY ts ASC LIMIT 1",
                (thread_id,),
            ).fetchone()
        if row:
            try:
                return json.loads(row[0]).get("created")
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def append_message(self, thread_id: str, role: str, content: str) -> None:
        self._append(thread_id, {"type": "message", "role": role, "content": content, "ts": time.time()})

    def _append(self, thread_id: str, event: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO events (thread_id, type, payload, ts) VALUES (?,?,?,?)",
                (thread_id, event.get("type", "event"), json.dumps(event), time.time()),
            )

    def load(self, thread_id: str) -> dict:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT payload FROM events WHERE thread_id=? ORDER BY ts ASC", (thread_id,)
            ).fetchall()
        if not rows:
            raise FileNotFoundError(f"no such thread: {thread_id}")
        messages = []
        for (payload,) in rows:
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "message":
                messages.append({"role": ev.get("role"), "content": ev.get("content", "")})
        return {"messages": messages}

    def list(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT thread_id, MIN(ts) AS created, MAX(ts) AS updated "
                "FROM events GROUP BY thread_id"
            ).fetchall()
        out = []
        for tid, created, updated in rows:
            try:
                data = self.load(tid)
            except FileNotFoundError:
                continue
            meta = {}
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT payload FROM events WHERE thread_id=? AND type='meta' "
                    "ORDER BY ts ASC LIMIT 1", (tid,)
                ).fetchone()
            if row:
                try:
                    meta = json.loads(row[0])
                except json.JSONDecodeError:
                    meta = {}
            messages = data["messages"]
            first_user = next(
                (m.get("content", "") for m in messages if m.get("role") == "user"), ""
            )
            out.append({
                "thread_id": tid,
                "provider": meta.get("provider", "?"),
                "model": meta.get("model", "?"),
                "created": created,
                "updated": updated,
                "n_messages": len(messages),
                "first_prompt": first_user[:80],
                "cwd": meta.get("cwd", ""),
            })
        out.sort(key=lambda e: e.get("updated") or 0)
        return out

    def latest(self) -> Optional[str]:
        entries = self.list()
        return entries[-1]["thread_id"] if entries else None

    def append(self, thread_id: str, event: dict) -> None:
        if event.get("type") == "meta":
            self.append_meta(
                thread_id,
                provider=event.get("provider", ""),
                model=event.get("model", ""),
                cwd=event.get("cwd", ""),
            )
        elif event.get("type") == "message":
            self.append_message(thread_id, event.get("role", ""), event.get("content", ""))


_STORES = {
    "jsonl": JsonlStore,
    "sqlite": SqliteStore,
}

VALID_STORES = sorted(_STORES)


def get_store(name: str, cfg=None, base=None):
    """Instantiate a session store by config name (unknown -> ValueError)."""
    if name not in _STORES:
        raise ValueError(
            f"unknown session_state strategy '{name}'. "
            f"Valid session_state strategies: {', '.join(VALID_STORES)}"
        )
    if name == "jsonl" and base is not None:
        return JsonlStore(base=base)
    if name == "sqlite" and base is not None:
        return SqliteStore(path=base)
    return _STORES[name]()

