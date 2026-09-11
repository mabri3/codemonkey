"""loop47 cycle 107 — the playbook store: quarantine by construction, the
deterministic delta merge, and byte-stability.

Each test pins a property the arc's design decisions depend on:

* new entries land `quarantined` and NOTHING loads them (`load_admitted`);
* the merge is idempotent and IN-PLACE: re-merging bumps `counter` and
  `last_seen` only — `text`, `status` and `provenance` are byte-stable
  (this is what 50 rounds of cycle 110 must not be able to erode);
* duplicates collapse by deterministic id; refusals are REPORTED with index
  and reason and write nothing;
* the store is gitignored by construction; a corrupt store is a loud error,
  never a silent empty.
"""

from __future__ import annotations

import json

import pytest

from codemonkey import playbook

PROV = {"run_id": "r-1", "session_id": "s-1", "taint_free": True}


def _delta(text="prefer rg over grep in this repo", kind="strategy",
           section="tools", prov=None):
    return {"kind": kind, "section": section, "text": text,
            "provenance": dict(prov or PROV)}


def test_merge_lands_quarantined_and_never_loads(tmp_path):
    rep = playbook.merge_deltas(tmp_path, [_delta()])
    assert rep["added"] == 1 and rep["updated"] == 0 and rep["refused"] == []
    rows = playbook.list_entries(tmp_path)
    assert rows[0]["status"] == "quarantined"
    assert playbook.load_admitted(tmp_path) == []


def test_remerge_bumps_counter_in_place_and_bytes_are_stable(tmp_path):
    playbook.merge_deltas(tmp_path, [_delta()])
    playbook.set_status(tmp_path, playbook.list_entries(tmp_path)[0]["id"],
                        "admitted", reason="test")
    before = playbook.list_entries(tmp_path)[0]
    rep = playbook.merge_deltas(tmp_path, [_delta()])
    after = playbook.list_entries(tmp_path)[0]
    assert rep["updated"] == 1 and rep["added"] == 0
    assert after["counter"] == before["counter"] + 1
    assert after["text"] == before["text"]
    assert after["status"] == "admitted"          # merge never demotes…
    assert after["provenance"] == before["provenance"]  # …or rewrites lineage
    # and it stays loaded — merging the same delta again changed no bytes of
    # the text that reaches the prompt
    assert [e["id"] for e in playbook.load_admitted(tmp_path)] == [before["id"]]


def test_same_batch_duplicates_collapse(tmp_path):
    rep = playbook.merge_deltas(tmp_path, [_delta(), _delta()])
    assert rep["added"] == 1 and rep["updated"] == 1
    rows = playbook.list_entries(tmp_path)
    assert len(rows) == 1 and rows[0]["counter"] == 2


def test_whitespace_normalization_is_the_identity(tmp_path):
    a = _delta(text="prefer   rg   over grep")
    b = _delta(text="prefer rg over grep\n")
    assert playbook.merge_deltas(tmp_path, [a, b])["added"] == 1
    assert playbook.list_entries(tmp_path)[0]["counter"] == 2


def test_refused_delta_is_reported_with_index_and_writes_nothing(tmp_path):
    bad_missing_prov = _delta()
    bad_missing_prov.pop("provenance")
    bad_kind = _delta(kind="rant")
    rep = playbook.merge_deltas(
        tmp_path, [_delta(), bad_missing_prov, bad_kind])
    assert rep["added"] == 1
    assert [r["index"] for r in rep["refused"]] == [1, 2]
    assert "provenance" in rep["refused"][0]["reason"]
    assert "kind" in rep["refused"][1]["reason"]
    assert len(playbook.list_entries(tmp_path)) == 1


def test_tainted_provenance_is_recorded_not_sanitized(tmp_path):
    prov = dict(PROV, taint_free=False, source="reflect:web_fetch")
    playbook.merge_deltas(tmp_path, [_delta(prov=prov)])
    e = playbook.list_entries(tmp_path)[0]
    assert e["provenance"]["taint_free"] is False
    assert e["provenance"]["source"] == "reflect:web_fetch"


def test_revoke_removes_and_show_refuses_after(tmp_path):
    playbook.merge_deltas(tmp_path, [_delta()])
    eid = playbook.list_entries(tmp_path)[0]["id"]
    res = playbook.revoke(tmp_path, eid)
    assert res == {"id": eid, "removed": True, "was": "quarantined"}
    assert playbook.list_entries(tmp_path) == []
    with pytest.raises(playbook.PlaybookError):
        playbook.get_entry(tmp_path, eid)


def test_status_gate_and_history(tmp_path):
    playbook.merge_deltas(tmp_path, [_delta()])
    eid = playbook.list_entries(tmp_path)[0]["id"]
    e = playbook.set_status(tmp_path, eid, "admitted", reason="operator")
    assert e["status"] == "admitted" and e["history"][-1]["to"] == "admitted"
    assert playbook.load_admitted(tmp_path)[0]["id"] == eid
    playbook.set_status(tmp_path, eid, "evicted", reason="later probe failed")
    assert playbook.load_admitted(tmp_path) == []
    with pytest.raises(playbook.PlaybookError):
        playbook.set_status(tmp_path, eid, "shipped")


def test_corrupt_store_is_a_loud_error(tmp_path):
    playbook.store_path(tmp_path).parent.mkdir(parents=True)
    playbook.store_path(tmp_path).write_text("{not json")
    with pytest.raises(playbook.PlaybookError) as ei:
        playbook.list_entries(tmp_path)
    assert "not valid JSON" in str(ei.value)
    # and an entry with an invalid status is equally unreadable
    playbook.store_path(tmp_path).write_text(json.dumps(
        {"version": 1, "entries": [{"id": "pb-x", "status": "blessed"}]}))
    with pytest.raises(playbook.PlaybookError) as ei:
        playbook.load_admitted(tmp_path)
    assert "invalid status" in str(ei.value)


def test_store_is_ignored_by_construction(tmp_path):
    playbook.merge_deltas(tmp_path, [_delta()])
    assert ".codemonkey/playbook/" in (tmp_path / ".gitignore").read_text()


def test_entry_id_is_deterministic_and_section_scoped(tmp_path):
    a = playbook.entry_id("strategy", "tools", "x  y")
    b = playbook.entry_id("strategy", "tools", "x y")
    c = playbook.entry_id("strategy", "other", "x y")
    assert a == b and a != c
