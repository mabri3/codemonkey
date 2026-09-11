"""Evolving playbook — quarantined, delta-curated (loop47, cycle 107).

The first store in this repo whose entries CHANGE the prompt through
ACCUMULATION rather than replacement: candidates arrive as small **deltas**,
and a deterministic, non-LLM merge integrates them — append new by id,
increment counters in place, collapse exact duplicates. There is no big
rewrite anywhere on this path, so the context-collapse failure mode (ACE
case study, arXiv 2510.04618: 18,282 → 122 tokens at 66.7% → 57.1%, below
the 63.7% no-adaptation baseline) is impossible BY CONSTRUCTION, not by
prompt instruction.

R-J applies with the same mechanics as `skills.py`:

* **Quarantined by construction.** A new entry's only possible state is
  `quarantined`; `load_admitted()` returns ONLY `admitted` entries. Merging
  never promotes; counters never promote; the gate is the only promotion.
* **Provenance is mandatory and structured** (run_id, session_id,
  taint_free) — a delta without it is refused with a reason, counted in the
  merge report, never silently dropped and never written.
* **Revocable in one command** (`revoke`) and the whole surface audit is the
  store file itself — plain JSON, no hidden state.

Byte-stability is the core invariant: an existing entry's `text` is NEVER
rewritten by a merge (later deltas with the same id bump `counter` and
`last_seen` only), which is the property cycle 110's 50-round regression
measures over 50 rounds.

Statuses: `quarantined` → `admitted` → `evicted`. As in `skills.py`, the
MECHANISM enforces no gate policy; policy lives in the cycles that ship
with probes (injection gate: cycle 109; consolidation: cycle 111).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

STORE_DIR = ".codemonkey/playbook"
STORE_FILE = "playbook.json"
STATUSES: tuple[str, ...] = ("quarantined", "admitted", "evicted")
KINDS: tuple[str, ...] = ("strategy", "pitfall", "schema", "tool_pattern",
                          "lesson")
_WS_RE = re.compile(r"\s+")


class PlaybookError(ValueError):
    """A store operation refused, with the reason."""


def store_root(workdir: str | Path) -> Path:
    return Path(workdir) / ".codemonkey" / "playbook"


def store_path(workdir: str | Path) -> Path:
    return store_root(workdir) / STORE_FILE


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def normalize_text(text: str) -> str:
    """Whitespace-collapsed form used for identity. Case is NOT folded —
    two texts differing only in case stay distinct entries."""
    return _WS_RE.sub(" ", (text or "").strip())


def entry_id(kind: str, section: str, text: str) -> str:
    """Deterministic id from (kind, section, normalized text). Re-merging
    the same delta therefore lands on the same entry (counter bump), which
    is what makes the merge idempotent AND the dedup exact."""
    basis = f"{kind}\x00{section}\x00{normalize_text(text)}"
    return "pb-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:10]


def ensure_ignored(workdir: str | Path) -> Path:
    """The store must not be committable by default (same rule as skills):
    ensures `.codemonkey/playbook/` is covered by the workspace `.gitignore`;
    idempotent."""
    gi = Path(workdir) / ".gitignore"
    line = STORE_DIR + "/"
    try:
        existing = gi.read_text() if gi.exists() else ""
    except OSError:
        existing = ""
    lines = [ln.strip() for ln in existing.splitlines()]
    if line in lines or ".codemonkey/" in lines or ".codemonkey" in lines:
        return gi
    sep = "" if existing.endswith("\n") or not existing else "\n"
    _atomic_write(gi, existing + sep + line + "\n")
    return gi


def validate_delta(delta: object, index: int) -> None:
    """Raise PlaybookError naming the first problem. A delta that fails any
    check is refused with its index and reason — never partially applied."""
    if not isinstance(delta, dict):
        raise PlaybookError(f"delta[{index}] must be a JSON object")
    kind = delta.get("kind")
    if kind not in KINDS:
        raise PlaybookError(
            f"delta[{index}]: kind {kind!r} is not one of {list(KINDS)}")
    text = delta.get("text")
    if not isinstance(text, str) or not normalize_text(text):
        raise PlaybookError(f"delta[{index}]: text must be non-empty")
    section = delta.get("section", "general")
    if not isinstance(section, str) or not section.strip():
        raise PlaybookError(f"delta[{index}]: section must be a non-empty string")
    prov = delta.get("provenance")
    if not isinstance(prov, dict):
        raise PlaybookError(
            f"delta[{index}]: provenance is required and must be an object — "
            f"nothing the agent writes about itself lands unlabeled (R-J)")
    for key in ("run_id", "session_id", "taint_free"):
        if key not in prov:
            raise PlaybookError(f"delta[{index}]: provenance is missing {key!r}")
    if not isinstance(prov["run_id"], str) or not prov["run_id"]:
        raise PlaybookError(f"delta[{index}]: provenance.run_id must be a "
                            f"non-empty string")
    if not isinstance(prov["session_id"], str):
        raise PlaybookError(f"delta[{index}]: provenance.session_id must be a "
                            f"string")
    if not isinstance(prov["taint_free"], bool):
        raise PlaybookError(f"delta[{index}]: provenance.taint_free must be a "
                            f"boolean")
    ev = delta.get("evidence")
    if ev is not None and (not isinstance(ev, list) or not all(
            isinstance(x, int) and not isinstance(x, bool) for x in ev)):
        raise PlaybookError(
            f"delta[{index}]: evidence must be a list of integer record "
            f"indexes (the journal positions a reflector derived it from)")


def normalize_delta(delta: dict) -> dict:
    """The stored shape of one validated delta. `evidence` is optional —
    a hand-written delta may carry none; a reflected one always does."""
    section = delta.get("section", "general")
    text = normalize_text(delta["text"])
    return {
        "id": delta.get("id") or entry_id(delta["kind"], section, text),
        "kind": delta["kind"],
        "section": section,
        "text": text,
        "evidence": sorted(int(x) for x in (delta.get("evidence") or [])),
        "provenance": {k: v for k, v in delta["provenance"].items()
                       if k in ("run_id", "session_id", "taint_free",
                                "source")},
    }


def read_store(workdir: str | Path) -> dict:
    """Read + validate the whole store. A missing file is an honest empty;
    a malformed file is a LOUD refusal (a store that hides breakage cannot
    be audited)."""
    path = store_path(workdir)
    if not path.exists():
        return {"version": 1, "entries": []}
    try:
        data = json.loads(path.read_text())
    except ValueError as exc:
        raise PlaybookError(
            f"{path} is not valid JSON: {exc} — refusing to read a corrupt "
            f"playbook") from None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise PlaybookError(
            f"{path}: store must be an object with an 'entries' list")
    for i, entry in enumerate(data["entries"]):
        if not isinstance(entry, dict) or "id" not in entry \
                or entry.get("status") not in STATUSES:
            raise PlaybookError(
                f"{path}: entry[{i}] is malformed or has an invalid status — "
                f"refusing to read a corrupt playbook")
    return data


def write_store(workdir: str | Path, data: dict) -> Path:
    ensure_ignored(workdir)
    path = store_path(workdir)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def list_entries(workdir: str | Path) -> list[dict]:
    """Every entry, honestly labeled. No store → `[]` (honest empty)."""
    return read_store(workdir)["entries"]


def load_admitted(workdir: str | Path) -> list[dict]:
    """The ONLY loader a prompt path may use: entries with status exactly
    `admitted`. Quarantined and evicted read as not loaded. No store → `[]`."""
    return [e for e in list_entries(workdir) if e.get("status") == "admitted"]


def merge_deltas(workdir: str | Path, deltas: list) -> dict:
    """Merge deltas through the deterministic, non-LLM path.

    Per delta: validate (refusals are REPORTED with index + reason and are
    never partially applied); compute the id; append a new entry as
    `quarantined` with counter 1, or bump `counter`/`last_seen` of the
    existing entry IN PLACE. `text`, `status` and `provenance` of an
    existing entry are never modified — first writer keeps provenance, and
    bytes are stable across any number of re-merges.

    Returns `{"added", "updated", "refused": [{"index", "reason"}],
    "total"}`.
    """
    data = read_store(workdir)
    entries = {e["id"]: e for e in data["entries"]}
    order = [e["id"] for e in data["entries"]]
    added = updated = 0
    refused: list[dict] = []
    for i, delta in enumerate(deltas or []):
        try:
            validate_delta(delta, i)
        except PlaybookError as exc:
            refused.append({"index": i, "reason": str(exc)})
            continue
        nd = normalize_delta(delta)
        existing = entries.get(nd["id"])
        if existing is None:
            entries[nd["id"]] = {
                "id": nd["id"], "kind": nd["kind"], "section": nd["section"],
                "text": nd["text"], "status": "quarantined", "counter": 1,
                "first_seen": _now(), "last_seen": _now(),
                "evidence": nd["evidence"],
                "provenance": nd["provenance"], "history": [],
            }
            order.append(nd["id"])
            added += 1
        else:
            existing["counter"] = int(existing.get("counter", 0)) + 1
            existing["last_seen"] = _now()
            updated += 1
    data["entries"] = [entries[eid] for eid in order]
    write_store(workdir, data)
    return {"added": added, "updated": updated, "refused": refused,
            "total": len(order)}


def get_entry(workdir: str | Path, entry_id_: str) -> dict:
    for entry in list_entries(workdir):
        if entry["id"] == entry_id_:
            return entry
    raise PlaybookError(f"no playbook entry with id {entry_id_!r}")


def set_status(workdir: str | Path, entry_id_: str, status: str,
               reason: str = "") -> dict:
    """Move an entry between statuses, journaling the move in the entry's
    own history. Policy (what may be admitted, when) belongs to the gate
    cycles, not this mechanism."""
    if status not in STATUSES:
        raise PlaybookError(f"status {status!r} is not one of {list(STATUSES)}")
    data = read_store(workdir)
    for entry in data["entries"]:
        if entry["id"] == entry_id_:
            entry.setdefault("history", []).append(
                {"from": entry["status"], "to": status, "at": _now(),
                 "reason": reason})
            entry["status"] = status
            write_store(workdir, data)
            return entry
    raise PlaybookError(f"no playbook entry with id {entry_id_!r}")


def revoke(workdir: str | Path, entry_id_: str) -> dict:
    """R-J revocation in one command: the entry is REMOVED from the store,
    so the next load cannot see it. The removal is journaled by the caller."""
    data = read_store(workdir)
    keep = [e for e in data["entries"] if e["id"] != entry_id_]
    if len(keep) == len(data["entries"]):
        raise PlaybookError(f"no playbook entry with id {entry_id_!r}")
    gone = [e for e in data["entries"] if e["id"] == entry_id_][0]
    data["entries"] = keep
    write_store(workdir, data)
    return {"id": entry_id_, "removed": True, "was": gone["status"]}


def playbook_thread(workdir: str | Path) -> str:
    """Journal thread for this workspace's playbook events — deterministic
    and readable, so \"the journal carries playbook.merged\" is checkable."""
    name = Path(workdir).resolve().name or "workspace"
    return f"playbook-{name}"


def store_stats(workdir: str | Path) -> dict:
    """Sizes for the boundedness claims (cycle 110): entries per status,
    total words, total counter. The 50-round regression reads these to show
    that accumulation grows monotonically and never collapses."""
    entries = list_entries(workdir)
    return {
        "entries": len(entries),
        "by_status": {s: sum(1 for e in entries if e.get("status") == s)
                      for s in STATUSES},
        "words": sum(len(str(e.get("text") or "").split()) for e in entries),
        "counter_total": sum(int(e.get("counter", 0)) for e in entries),
    }


# --- the reflector: journal → evidence-cited deltas (cycle 108) --------------
#
# Where candidates COME FROM, deterministically. ACE's Reflector distills
# insights with an LLM; this repo already owns a deterministic classifier for
# the same signal (failclass.py, AgentRx labels), so the repo-sized reflector
# is a PURE PASS over journal records: no model call anywhere, same records →
# byte-identical deltas, and it NEVER merges — the store is untouched by
# reflection (merge is the explicit verb, run by the operator).

TAINT_SOURCE_TOOLS = ("web_fetch", "shell")


def reflect(records: list, *, thread: str = "") -> list[dict]:
    """Journal records → candidate deltas citing the record indexes they
    derive from.

    Failure outcomes are classified by the existing taxonomy and grouped per
    (tool, category): one candidate delta per group, `kind: pitfall`,
    `evidence` = the sorted record indexes. Transient-infrastructure and
    uncoded classes stay UNMAPPED and produce no candidate — a delta that
    says "something failed" teaches nothing. Determinism is total: the
    output is a pure function of `records` (the same thread reflects to the
    same bytes), and the store is never read or written here.

    Taint posture is coarse (loop 49 refines it): a group whose contributing
    records include a source tool (web_fetch / shell stdout) is marked
    `taint_free: False`. The delta's own text is always a template over
    (tool, category, reason, count) — never the untrusted output itself.
    """
    from . import failclass as fc

    groups: dict[tuple[str, str], dict] = {}
    for i, rec in enumerate(records or []):
        if not isinstance(rec, dict) or rec.get("type") != "outcome":
            continue
        if str(rec.get("status") or "") != "error":
            continue
        cat, reason = fc.classify_record(rec)
        if cat == fc.UNMAPPED:
            continue
        tool = str(rec.get("tool") or "?")
        g = groups.setdefault((tool, cat),
                              {"indexes": [], "reason": reason, "taint": False})
        g["indexes"].append(i)
        if tool in TAINT_SOURCE_TOOLS:
            g["taint"] = True

    deltas: list[dict] = []
    for (tool, cat) in sorted(groups):
        g = groups[(tool, cat)]
        n = len(g["indexes"])
        deltas.append({
            "kind": "pitfall",
            "section": "failures",
            "text": f"{tool} → {cat}: {g['reason']}; {n} occurrence(s) on "
                    f"thread {thread or '?'}",
            "evidence": sorted(g["indexes"]),
            "provenance": {
                "run_id": f"reflect:{thread or 'unknown'}",
                "session_id": thread or "",
                "taint_free": not g["taint"],
                "source": f"reflect:{thread or 'unknown'}",
            },
        })
    return deltas
