"""Cycle 96 (loop 41, R41-C5): partial-application counter.

The 91F3 lesson applies directly: a test that never presents the
discriminating case proves nothing. Every label gets its discriminator:
PARTIAL requires a failure AFTER a landing (91F1 ordering); ABORTED is the
failure-with-nothing-landed control; SINGLE/CLEAN are the no-failure
controls.
"""

from __future__ import annotations

from codemonkey.partial import classify_thread, summarize


def _outcome(tool, key, status, ts, error_class=None):
    r = {"type": "outcome", "tool": tool, "key": key, "status": status,
         "ts": ts}
    if error_class:
        r["error_class"] = error_class
    return r


def test_no_edits():
    c = classify_thread([{"type": "intent", "tool": "shell", "key": "k"}])
    assert c["label"] == "NO_EDITS"


def test_single_clean():
    c = classify_thread([_outcome("write_file", "a", "ok", 1.0)])
    assert c["label"] == "SINGLE" and c["landed"] == [("write_file", "a")]


def test_multi_all_ok_is_clean():
    recs = [_outcome("write_file", "a", "ok", 1.0),
            _outcome("edit_file", "b", "ok", 2.0)]
    c = classify_thread(recs)
    assert c["label"] == "CLEAN" and len(c["landed"]) == 2


def test_failure_after_landing_is_partial_and_names_keys():
    recs = [_outcome("write_file", "a", "ok", 1.0),
            _outcome("edit_file", "b", "error", 2.0, "tool-error")]
    c = classify_thread(recs)
    assert c["label"] == "PARTIAL"
    assert c["first_landed"] == ("write_file", "a")
    assert c["failed"] == [(("edit_file", "b"), "tool-error")]


def test_failure_with_nothing_landed_is_aborted_not_partial():
    recs = [_outcome("write_file", "a", "error", 1.0, "denied")]
    c = classify_thread(recs)
    assert c["label"] == "ABORTED"
    assert c["landed"] == []


def test_replayed_counts_as_landed_not_duplicate():
    recs = [_outcome("write_file", "a", "ok", 1.0),
            _outcome("write_file", "a", "replayed", 2.0),
            _outcome("edit_file", "b", "ok", 3.0)]
    c = classify_thread(recs)
    assert c["label"] == "CLEAN" and len(c["landed"]) == 2


def test_failure_before_first_landing_does_not_arm():
    # 91F1 ordering: only failures AFTER the first landing count. A failure
    # at ts 1.0 precedes the landing at ts 2.0 → not partial evidence.
    recs = [_outcome("edit_file", "b", "error", 1.0, "tool-error"),
            _outcome("write_file", "a", "ok", 2.0)]
    c = classify_thread(recs)
    assert c["label"] == "SINGLE"


def test_empty_population_rate_is_none_not_zero():
    # Denominator zero → no rate exists. 0.0 would claim a measured absence.
    s = summarize({"t1": classify_thread([])})
    assert s["multi_edit"] == 0 and s["rate"] is None


def test_summarize_rate_is_partial_over_multi_edit():
    classified = {
        "t1": classify_thread([_outcome("write_file", "a", "ok", 1.0),
                               _outcome("edit_file", "b", "ok", 2.0)]),
        "t2": classify_thread([_outcome("write_file", "a", "ok", 1.0),
                               _outcome("edit_file", "b", "error", 2.0,
                                          "tool-error")]),
        "t3": classify_thread([_outcome("write_file", "a", "ok", 1.0)]),
        "t4": classify_thread([]),
    }
    s = summarize(classified)
    assert s == {"threads": 4, "with_edits": 3, "multi_edit": 2,
                 "partial": 1, "partial_threads": ["t2"], "rate": 0.5,
                 "labels": {"t1": "CLEAN", "t2": "PARTIAL",
                            "t3": "SINGLE", "t4": "NO_EDITS"}}
