"""Durable job files (loop12, cycle 43).

Workflow state ≠ session state: a job is a durable, resumable representation
of "this task, its steps, what is done, what is next" at
~/.codemonkey/jobs/<id>.json:

  {"id": ..., "goal": ..., "steps": [{"id": ..., "status": "pending"|
   "done"|"failed", "note": ...}], "created": ..., "updated": ...}

All writes are atomic (tmp + os.replace) so a crash mid-write never corrupts
a job. Single-writer per job (no locking yet — R13+ if fan-out jobs land).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

STATUSES = ("pending", "done", "failed")


def jobs_dir() -> Path:
    d = Path.home() / ".codemonkey" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_path(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, path)  # atomic on POSIX and Windows


def create(goal: str, steps: list[str], *, job_id: Optional[str] = None) -> dict:
    now = time.time()
    if job_id:
        jid = job_id
    else:
        import uuid as _u

        jid = f"job-{time.strftime('%Y%m%d-%H%M%S')}-{_u.uuid4().hex[:6]}"
    job = {
        "id": jid,
        "goal": goal,
        "steps": [{"id": s, "status": "pending", "note": ""} for s in steps],
        "created": now,
        "updated": now,
    }
    _atomic_write(job_path(jid), job)
    return job


def load(job_id: str) -> Optional[dict]:
    try:
        return json.loads(job_path(job_id).read_text())
    except (OSError, json.JSONDecodeError):
        return None


def save(job: dict) -> dict:
    job["updated"] = time.time()
    _atomic_write(job_path(job["id"]), job)
    return job


def set_step(job_id: str, step_id: str, status: str, note: str = "") -> Optional[dict]:
    """Transition one step. Unknown job/step or bad status -> None."""
    if status not in STATUSES:
        return None
    job = load(job_id)
    if job is None:
        return None
    for s in job["steps"]:
        if s["id"] == step_id:
            s["status"] = status
            if note:
                s["note"] = note
            return save(job)
    return None


def list_jobs() -> list[dict]:
    out = []
    for p in jobs_dir().glob("*.json"):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(out, key=lambda j: j.get("created", 0))


def render(job: dict) -> str:
    """Human-readable render — also the injection text for exec --job."""
    lines = [f"job {job['id']}: {job['goal']}"]
    for s in job["steps"]:
        mark = {"pending": "[ ]", "done": "[x]", "failed": "[!]"}.get(s["status"], "[?]")
        note = f" — {s['note']}" if s.get("note") else ""
        lines.append(f"  {mark} {s['id']}{note}")
    return "\n".join(lines)
