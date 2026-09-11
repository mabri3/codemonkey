"""loop47 cycle 110 — grow-and-refine under 50 rounds: the collapse regression.

ACE's case study (arXiv 2510.04618): a system that REWRITES its accumulated
context each adaptation step went 18,282 → 122 tokens at step 61 with accuracy
66.7% → 57.1% — BELOW the 63.7% no-adaptation baseline. This repo's merge
cannot do that BY CONSTRUCTION (append + counter-in-place + exact dedup, no
rewrite anywhere); the regression below proves it, and a REWRITE-style control
implementation must FAIL the same regression — the control that proves the
regression can actually see the defect.

The regression, in four predicates, over a store access adapter:
  1. the round-1 entry is still present and its text is BYTE-IDENTICAL;
  2. no two entries carry the same (normalized) text — dedup, not sprawl;
  3. the recurring delta's counter equals the number of rounds (in-place
     counting, not re-append);
  4. growth is monotone: words after the last round >= words after the first.
"""

from __future__ import annotations

import json

from codemonkey import playbook

ROUNDS = 50
PROV = {"run_id": "r", "session_id": "s", "taint_free": True}


def _deltas_for(r: int) -> list[dict]:
    out = [
        {"kind": "strategy", "section": "growth",
         "text": f"round {r} rule", "provenance": dict(PROV)},
        {"kind": "pitfall", "section": "recurring",
         "text": "recurring lesson alpha", "provenance": dict(PROV)},
    ]
    if r % 10 == 9:  # a whitespace twin — must normalize onto the same entry
        out.append({"kind": "pitfall", "section": "recurring",
                    "text": "recurring  lesson   alpha", "provenance": dict(PROV)})
    return out


class RealStore:
    """Adapter over the real, on-disk playbook."""

    def __init__(self, workdir):
        self.workdir = workdir

    def merge_round(self, r):
        return playbook.merge_deltas(self.workdir, _deltas_for(r))

    def entry(self, eid):
        for e in playbook.list_entries(self.workdir):
            if e["id"] == eid:
                return e
        return None

    def texts(self):
        return [e["text"] for e in playbook.list_entries(self.workdir)]

    def stats(self):
        return playbook.store_stats(self.workdir)


class RewriteControl:
    """The naive house: a full REWRITE each round — brevity bias (texts
    truncated) and context collapse (older entries dropped). This is the
    shape the regression exists to catch; it must FAIL the predicates."""

    def __init__(self):
        self.entries: list[dict] = []

    def merge_round(self, r):
        for d in _deltas_for(r):
            eid = playbook.entry_id(d["kind"], d["section"], d["text"])
            existing = next((e for e in self.entries if e["id"] == eid), None)
            if existing is None:
                self.entries.append({"id": eid, "text": d["text"], "counter": 1})
            else:
                existing["counter"] += 1
        # the rewrite: keep only the last 10, truncate every text
        self.entries = self.entries[-10:]
        for e in self.entries:
            e["text"] = e["text"][:20].strip()

    def entry(self, eid):
        return next((e for e in self.entries if e["id"] == eid), None)

    def texts(self):
        return [e["text"] for e in self.entries]

    def stats(self):
        return {"entries": len(self.entries),
                "words": sum(len(e["text"].split()) for e in self.entries)}


def regression_violations(store) -> list[str]:
    """Run the 50 rounds and return the broken predicates ([] = passed)."""
    round0_id = playbook.entry_id("strategy", "growth", "round 0 rule")
    recur_id = playbook.entry_id("pitfall", "recurring", "recurring lesson alpha")
    violations: list[str] = []
    round0_bytes: str | None = None
    words_first: int | None = None
    for r in range(ROUNDS):
        store.merge_round(r)
        if r == 0:
            e = store.entry(round0_id)
            round0_bytes = json.dumps(e, sort_keys=True) if e else None
            words_first = store.stats()["words"]
    e = store.entry(round0_id)
    if e is None:
        violations.append("round-1 entry MISSING (context collapse)")
    elif json.dumps(e, sort_keys=True) != round0_bytes:
        violations.append("round-1 entry CHANGED bytes (rewrite eroded it)")
    texts = store.texts()
    if len(texts) != len(set(texts)):
        violations.append("duplicate texts present (dedup failed)")
    rec = store.entry(recur_id)
    if rec is None or rec["counter"] != ROUNDS + 5:  # 50 rounds + 5 twin repeats
        violations.append(f"recurring counter wrong: "
                          f"{rec and rec['counter']} != {ROUNDS + 5}")
    if store.stats()["words"] < (words_first or 0):
        violations.append("size SHRANK across the run (lossy rewrite)")
    return violations


def test_grow_and_refine_50_rounds_never_collapses(tmp_path):
    store = RealStore(tmp_path)
    violations = regression_violations(store)
    assert violations == [], f"regression violated: {violations}"
    # the numbers, pinned: 50 distinct round rules + 1 recurring entry; the
    # recurring one has absorbed 50 merges + 5 whitespace twins
    st = store.stats()
    assert st["entries"] == ROUNDS + 1
    assert st["counter_total"] == ROUNDS + (ROUNDS + 5)


def test_the_rewrite_control_fails_the_same_regression():
    control = RewriteControl()
    violations = regression_violations(control)
    assert violations, "the regression cannot see the collapse it exists for"
    assert any("MISSING" in v or "CHANGED" in v for v in violations), violations


def test_remerge_after_the_run_still_changes_no_bytes(tmp_path):
    store = RealStore(tmp_path)
    store.merge_round(0)
    eid = playbook.entry_id("strategy", "growth", "round 0 rule")
    before = store.entry(eid)
    assert before is not None
    playbook.merge_deltas(tmp_path, _deltas_for(0) * 3)  # three more merges
    after = store.entry(eid)
    assert after is not None
    assert after["text"] == before["text"]
    assert after["counter"] == before["counter"] + 3
    assert playbook.store_stats(tmp_path)["entries"] == 2  # still no sprawl
