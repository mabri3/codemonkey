"""Lessons store (loop13, cycle 45).

Learning from the run history, safely: lessons are mined from journal failure
classes, tagged for scoped retrieval (avoiding experience-following — ACL
2026.acl-long.27), and only injected once verified by an eval run
(execute-distill-verify — arxiv 2606.24428). Same atomic-write pattern as
jobs.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

_LESSON_FILE = "lessons.json"


def lessons_path() -> Path:
    d = Path.home() / ".codemonkey"
    d.mkdir(parents=True, exist_ok=True)
    return d / _LESSON_FILE


def _atomic_write(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    import os

    os.replace(tmp, path)


def load_all() -> list[dict]:
    try:
        return json.loads(lessons_path().read_text())
    except (OSError, json.JSONDecodeError):
        return []


def save_all(entries: list[dict]) -> None:
    _atomic_write(lessons_path(), entries)


def add(text: str, *, tool: str = "*", error_class: str = "*",
        verified: bool = False) -> dict:
    entries = load_all()
    entry = {
        "id": f"les-{int(time.time())}-{len(entries) + 1}",
        "tags": {"tool": tool, "error_class": error_class},
        "text": text,
        "verified": verified,
        "created": time.time(),
    }
    entries.append(entry)
    save_all(entries)
    return entry


def extract_drafts(journal_classes: dict[str, int], *,
                   threshold: int = 2) -> list[dict]:
    """Mine journal class counts into DRAFT lesson entries (verified=False).
    One draft per class over the threshold; text is a human-curatable
    template."""
    drafts = []
    for cls, count in journal_classes.items():
        if cls == "ok" or count < threshold:
            continue
        drafts.append(add(
            f"Recurring {cls} failures ({count}x). Review the related tool "
            f"calls and record the mitigation here.",
            tool="*", error_class=cls, verified=False))
    return drafts


def retrieve(task_text: str, *, min_overlap: int = 1,
             verified_only: bool = True) -> list[dict]:
    """Scoped retrieval: lessons whose tags overlap the task text keywords.
    Verified-only by default (experience-following guard)."""
    task_l = task_text.lower()
    out = []
    for entry in load_all():
        if verified_only and not entry.get("verified"):
            continue
        score = 0
        for tag in entry.get("tags", {}).values():
            t = str(tag).lower()
            if t and t != "*" and t in task_l:
                score += 1
        if score >= min_overlap:
            out.append(entry)
    return out


def mark_verified(lesson_id: str, verified: bool = True) -> Optional[dict]:
    entries = load_all()
    for e in entries:
        if e["id"] == lesson_id:
            e["verified"] = verified
            save_all(entries)
            return e
    return None
