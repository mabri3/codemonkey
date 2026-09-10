"""Evidence pack + hash-chained journal (loop45, cycle 105).

A claim in a report is worth exactly what its evidence is worth, and evidence
stored in the same file as the claim is worth very little. This module builds
a PACK: the run's claims, each explicitly bound to the journal records that
produced it, with every record hash-chained so editing any one of them breaks
verification.

    h_0 = "genesis"
    h_i = sha256(h_{i-1} || canonical_json(record_i))

The pack stores every link AND the head. Verification is TWO independent
checks, and both must pass:

1. **INTERNAL** — recompute the chain from the pack's own records. A record
   that was edited, deleted or reordered cannot reproduce the stored head.
   This is what makes the pack tamper-evident as a document.
2. **AGAINST THE LIVE JOURNAL** — re-derive from the journal on disk. If the
   journal has moved on, or was edited after the pack was cut, the heads
   disagree.

A pack that passed only (1) would be a consistent fiction; a pack that passed
only (2) could not be carried to another machine. Both, or the pack does not
verify.

Redaction happens BEFORE hashing: the pack is a document that gets copied,
mailed and committed, so a secret in a journaled command must never be sealed
into it. Because redaction is part of pack construction, the chain commits to
the REDACTED bytes — which is the honest thing for a document whose whole
purpose is to be handed to someone else.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

GENESIS = "genesis"


def canonical(record: dict) -> str:
    """Stable bytes for a record. Key order must not change the hash, and the
    same record must hash the same way on any machine."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      default=str)


def link(prev_hash: str, record: dict) -> str:
    payload = (prev_hash + "\x1f" + canonical(record)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_chain(records: list[dict]) -> list[str]:
    chain: list[str] = []
    prev = GENESIS
    for rec in records:
        prev = link(prev, rec)
        chain.append(prev)
    return chain


def _redact_records(records: list[dict], needles: list[str]) -> tuple[list[dict], int]:
    """Scrub secret-shaped and configured needle strings out of every string
    field before anything is hashed or written."""
    from .redact import redact_text

    hits = 0
    out: list[dict] = []

    def scrub(value):
        nonlocal hits
        if isinstance(value, str):
            cleaned, n = redact_text(value, needles)
            hits += n
            return cleaned
        if isinstance(value, dict):
            return {k: scrub(v) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(v) for v in value]
        return value

    for rec in records:
        out.append(scrub(dict(rec)))
    return out, hits


def claims_from(records: list[dict]) -> list[dict]:
    """The run's observable claims, each citing the records it rests on.

    Derived, never invented: every claim here is a statement about a journal
    record that exists in this pack, and carries that record's index. A claim
    with no evidence index would be exactly the defect this arc keeps finding.
    """
    claims: list[dict] = []
    for i, rec in enumerate(records):
        tool = rec.get("tool") or rec.get("type") or "?"
        status = rec.get("status") or "unknown"
        key = rec.get("key") or ""
        chain = rec.get("chain") or rec.get("command") or ""
        detail = f"{tool} {status}"
        if chain:
            detail += f": {str(chain)[:80]}"
        elif key:
            detail += f" (id {str(key)[:12]})"
        claims.append({"kind": "journal-record", "text": detail,
                       "evidence": [i]})
    return claims


def pack(thread_id: str, *, workdir: Optional[Path] = None,
         needles: Optional[list[str]] = None,
         version: str = "") -> dict:
    """Build the evidence pack for a thread. Raises FileNotFoundError if the
    thread has no journal — an empty pack for a run that never happened would
    be a claim about nothing."""
    from . import journal as journal_mod

    raw = journal_mod.read_thread(thread_id)
    if not raw:
        raise FileNotFoundError(f"no journal records for thread {thread_id!r}")
    records, redactions = _redact_records(raw, needles or [])
    chain = build_chain(records)
    return {
        "pack_version": 1,
        "thread_id": thread_id,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "codemonkey_version": version,
        "workdir": str(workdir) if workdir else "",
        "redactions": redactions,
        "records": records,
        "chain": chain,
        "head": chain[-1] if chain else GENESIS,
        "claims": claims_from(records),
        "counts": {"records": len(records), "claims": len(records)},
    }


def verify(pack_doc: dict, journal_records: Optional[list[dict]] = None) -> dict:
    """Both checks. `ok` is True only when every applicable check passes.

    `journal_records` is optional: pass the live journal to also check that
    the pack still describes the run on disk.
    """
    problems: list[str] = []
    records = list(pack_doc.get("records") or [])
    stored = list(pack_doc.get("chain") or [])

    # (1) internal consistency — the pack's own bytes must reproduce its head
    recomputed = build_chain(records)
    internal = recomputed == stored
    if not internal:
        if len(recomputed) != len(stored):
            problems.append(
                f"chain length {len(recomputed)} != stored {len(stored)} — a "
                f"record was added or removed")
        else:
            bad = [i for i, (a, b) in enumerate(zip(recomputed, stored))
                   if a != b]
            problems.append(
                f"chain broken at record(s) {bad} — the pack's bytes do not "
                f"reproduce its own head")
    head_ok = (pack_doc.get("head") == (stored[-1] if stored else GENESIS))
    if not head_ok:
        problems.append("head does not match the last stored link")

    # (2) the pack against the run on disk
    journal: Optional[bool] = None
    if journal_records is not None:
        live, _ = _redact_records(list(journal_records),
                                  [])          # already-redacted on disk
        live_chain = build_chain(live)
        journal = bool(live_chain) and live_chain[-1] == pack_doc.get("head")
        if not journal:
            problems.append(
                "the journal on disk does not reproduce this pack's head — "
                "the run was edited or extended after the pack was cut")

    return {"ok": not problems, "internal": internal, "journal": journal,
            "problems": problems,
            "records": len(records),
            "head": pack_doc.get("head", "")}


def verify_against_journal(pack_doc: dict) -> dict:
    """Convenience: verify() including the live-journal check."""
    from . import journal as journal_mod

    thread = pack_doc.get("thread_id", "")
    return verify(pack_doc, journal_mod.read_thread(thread) if thread else [])


def render(pack_doc: dict) -> str:
    lines = [
        f"evidence pack v{pack_doc.get('pack_version')} — thread "
        f"{pack_doc.get('thread_id')}",
        f"generated {pack_doc.get('generated')}  records "
        f"{pack_doc.get('counts', {}).get('records')}  redactions "
        f"{pack_doc.get('redactions', 0)}",
        f"head {pack_doc.get('head')}",
        "",
        "claims (each cites the records it rests on):",
    ]
    for c in (pack_doc.get("claims") or [])[:20]:
        lines.append(f"  [{','.join(str(i) for i in c['evidence'])}] {c['text']}")
    n = len(pack_doc.get("claims") or [])
    if n > 20:
        lines.append(f"  … {n - 20} more")
    return "\n".join(lines)
