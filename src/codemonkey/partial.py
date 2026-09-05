"""Partial-application counter (loop 41, cycle 96 — R41 candidate C5).

Counts the failure mode BEFORE touching application semantics: no baseline,
no claim. Operates post-hoc over journal thread records (the same records
`journal.read_thread` returns), so historical runs are measurable without
re-running them.

Operational definitions (pre-plan-object — stated plainly):
- A "hunk landed" = an edit-tool outcome (`write_file`, `edit_file`) with
  status `ok` or `replayed`, keyed by distinct (tool, args-hash) key. The
  journal never stores raw paths, so distinct keys proxy distinct edits; a
  file edited twice counts twice. The plan object (C97) will make
  planned-vs-landed exact — this counter does not claim that precision.
- PARTIAL = ≥1 hunk landed AND an edit outcome with status `error` at a
  later timestamp than the first landed hunk. The ordering requirement is
  the 91F1 lesson: a failure with nothing landed is ABORTED, not partial,
  and the report names WHICH key failed after WHICH landed key so the label
  is checkable against the evidence.
- Verifier outcome per thread is NOT in the journal (no verify tool
  records), so "tests pass by accident" is unmeasurable from history and is
  NOT claimed here — C97's plan object carries the verifier half.

Labels: NO_EDITS / SINGLE / CLEAN / PARTIAL / ABORTED.
"""

from __future__ import annotations

EDIT_TOOLS = ("write_file", "edit_file")
LANDED = ("ok", "replayed")


def classify_thread(records: list[dict]) -> dict:
    """Classify one thread's journal records. Pure function over evidence."""
    outcomes = [r for r in records
                if r.get("type") == "outcome" and r.get("tool") in EDIT_TOOLS]
    if not outcomes:
        return {"label": "NO_EDITS", "landed": [], "failed": []}
    landed: dict[tuple, float] = {}
    failed: list[dict] = []
    for r in outcomes:
        key = (r.get("tool"), r.get("key"))
        ts = r.get("ts", 0)
        if r.get("status") in LANDED:
            if key not in landed or ts < landed[key]:
                landed[key] = ts
        elif r.get("status") == "error":
            failed.append({"key": key, "ts": ts,
                           "error_class": r.get("error_class")})
    landed_keys = sorted(landed, key=lambda k: landed[k])
    if not landed_keys:
        return {"label": "ABORTED", "landed": [],
                "failed": [(f["key"], f["error_class"]) for f in failed]}
    if len(landed_keys) == 1 and not failed:
        return {"label": "SINGLE", "landed": landed_keys, "failed": []}
    first_landed_ts = landed[landed_keys[0]]
    late_failures = [f for f in failed if f["ts"] > first_landed_ts]
    if late_failures:
        return {"label": "PARTIAL", "landed": landed_keys,
                "failed": [(f["key"], f["error_class"]) for f in late_failures],
                "first_landed": landed_keys[0]}
    if len(landed_keys) >= 2:
        return {"label": "CLEAN", "landed": landed_keys, "failed": []}
    return {"label": "SINGLE", "landed": landed_keys,
            "failed": [(f["key"], f["error_class"]) for f in failed]}


def summarize(classified: dict[str, dict]) -> dict:
    """Baseline rate over per-thread classifications.

    The population is runs that ATTEMPTED >= 2 distinct edits (landed or
    failed) — a 1-landed + 1-failed run is partial application, and a
    landed-only gate would drop exactly the failure mode being counted.
    Single-edit and no-edit threads are reported, never folded in.
    """
    multi = {t: c for t, c in classified.items()
             if len(set(c["landed"]) | {k for k, _ in c["failed"]}) >= 2}
    partial = {t: c for t, c in multi.items() if c["label"] == "PARTIAL"}
    # No multi-edit runs → no rate exists. 0.0 would claim a measured
    # absence; None states the denominator is zero.
    rate = (len(partial) / len(multi)) if multi else None
    return {
        "threads": len(classified),
        "with_edits": sum(1 for c in classified.values() if c["landed"]),
        "multi_edit": len(multi),
        "partial": len(partial),
        "partial_threads": sorted(partial),
        "rate": rate,
        "labels": {t: c["label"] for t, c in classified.items()},
    }
