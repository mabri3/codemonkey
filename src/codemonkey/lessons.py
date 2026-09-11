"""Lessons (loop13, cycle 45) — now a SHIM over the playbook (loop47, C111).

R-A consolidation: the `~/.codemonkey/lessons.json` store is **DELETED INTO
the playbook** — one agent-authored accumulation surface, not two. The
semantics carry over unchanged:

  * verified flag -> status `admitted` (the eval gate: a draft is mined,
    an eval run verifies it, only then does it inject);
  * tags {tool, error_class} -> the entry SECTION, losslessly encoded
    (`tool` or `tool|error_class`) so retrieval scoring round-trips exactly;
  * drafts stay drafts (quarantined) and `retrieve` stays tag-scoped.

The moved citations: the experience-following guard (ACL 2026.acl-long.27)
is `retrieve`'s tag-scoped retrieval; execute-distill-verify (arxiv
2606.24428) is draft -> eval -> `admitted` in the store's own history.
`codemonkey playbook migrate-lessons` moves an existing lessons file through
the parity gate (the old file is ARCHIVED, not destroyed); this module keeps
the old call shapes working against the new store.
"""

from __future__ import annotations

from pathlib import Path

from . import playbook as _pb


def _view(entry: dict) -> dict:
    """Playbook lesson entry -> the legacy lesson shape callers expect."""
    return {
        "id": entry["id"],
        "tags": _pb.parse_section(entry.get("section", "*")),
        "text": entry["text"],
        "verified": entry.get("status") == "admitted",
        "created": entry.get("first_seen", ""),
    }


def load_all(workdir=None) -> list[dict]:
    wd = Path(workdir) if workdir else Path.cwd()
    return [_view(e) for e in _pb.list_entries(wd) if e.get("kind") == "lesson"]


def add(text: str, *, tool: str = "*", error_class: str = "*",
        verified: bool = False) -> dict:
    cwd = Path.cwd()
    section = _pb.lesson_section({"tool": tool, "error_class": error_class})
    _pb.merge_deltas(cwd, [{
        "kind": "lesson", "section": section, "text": text,
        "provenance": {"run_id": "lessons.add", "session_id": "",
                       "taint_free": True, "source": "lessons.add"}}])
    eid = _pb.entry_id("lesson", section, text)
    if verified:
        try:
            _pb.set_status(cwd, eid, "admitted", reason="added verified")
        except _pb.PlaybookError:
            pass
    return _view(_pb.get_entry(cwd, eid))


def extract_drafts(journal_classes: dict, *,
                   threshold: int = 2) -> list[dict]:
    """Mine journal class counts into DRAFT lesson entries (quarantined).
    One draft per class over the threshold; text is a human-curatable
    template. (Unchanged shape; the store behind `add` is the playbook.)"""
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
    Verified-only by default (experience-following guard). Same scoring as
    the loop13 store carried — over the playbook's lesson entries."""
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


def mark_verified(lesson_id: str, verified: bool = True):
    """Flip the verified flag — i.e. admit/quarantine the playbook entry.
    Returns the legacy-shaped entry, or None when no such lesson exists."""
    cwd = Path.cwd()
    try:
        e = _pb.get_entry(cwd, lesson_id)
    except _pb.PlaybookError:
        return None
    if e.get("kind") != "lesson":
        return None
    e = _pb.set_status(cwd, lesson_id,
                       "admitted" if verified else "quarantined",
                       reason="mark_verified" if verified else "unverified")
    return _view(e)
