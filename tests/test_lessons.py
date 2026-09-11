"""Cycle 45 (loop13) lessons semantics — carried over the playbook store.

R-A (loop47 C111): the lessons STORE is deleted into the playbook; these
are the same behavioral claims as the loop13 suite, re-pointed at the new
store (workspace-scoped now, not `~/.codemonkey`), plus the two behaviors
the store change brings on purpose: identical adds collapse into one entry
(dedup is the playbook's doctrine) and tags round-trip losslessly through
the section encoding.
"""

from __future__ import annotations

import pytest

from codemonkey import playbook
from codemonkey.lessons import add, extract_drafts, load_all, mark_verified, retrieve


@pytest.fixture()
def lhome(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_add_and_load(lhome):
    e = add("prefer streaming with a deadline", tool="shell", error_class="timeout")
    all_ = load_all()
    assert len(all_) == 1 and all_[0]["text"] == e["text"]
    assert e["verified"] is False
    assert e["tags"] == {"tool": "shell", "error_class": "timeout"}


def test_extract_drafts_from_journal_classes(lhome):
    drafts = extract_drafts({"timeout": 5, "ok": 10, "parse": 1}, threshold=2)
    assert len(drafts) == 1
    assert drafts[0]["tags"]["error_class"] == "timeout"
    assert drafts[0]["verified"] is False  # draft, not trusted
    # and the underlying entry is quarantined, per the store
    entry = playbook.get_entry(lhome, drafts[0]["id"])
    assert entry["status"] == "quarantined"


def test_scoped_retrieval(lhome):
    add("use streaming deadlines for shell", tool="shell", error_class="timeout",
        verified=True)
    add("nothing about this task", tool="repo_map", error_class="parse",
        verified=True)
    hits = retrieve("shell timeout issue on big output")
    assert len(hits) == 1
    assert "streaming" in hits[0]["text"]


def test_unverified_excluded(lhome):
    add("draft lesson only", tool="shell", error_class="timeout", verified=False)
    assert retrieve("shell timeout") == []


def test_no_overlap_no_inject(lhome):
    add("unrelated lesson", tool="repo_map", error_class="parse", verified=True)
    assert retrieve("completely different topic") == []


def test_store_writes_stay_atomic_under_stray_tmp(lhome):
    add("first", verified=True)
    tmp = playbook.store_path(lhome).with_name(playbook.STORE_FILE + ".tmp")
    tmp.write_text("garbage")
    add("second", verified=True)
    assert len(load_all()) == 2
    assert playbook.read_store(lhome)["entries"]  # readable


def test_mark_verified_roundtrip(lhome):
    e = add("lesson", tool="shell", error_class="timeout")
    assert mark_verified(e["id"])["verified"] is True
    assert load_all()[0]["verified"] is True
    assert mark_verified(e["id"], verified=False)["verified"] is False
    assert mark_verified("nope") is None


def test_identical_adds_collapse_into_one_entry(lhome):
    a = add("same text", tool="shell", error_class="timeout", verified=True)
    b = add("same text", tool="shell", error_class="timeout", verified=True)
    assert a["id"] == b["id"]
    rows = [x for x in playbook.list_entries(lhome) if x["kind"] == "lesson"]
    assert len(rows) == 1 and rows[0]["counter"] == 2


def test_tag_encoding_round_trips(lhome):
    assert playbook.lesson_section({"tool": "shell"}) == "shell"
    assert playbook.lesson_section({"tool": "shell", "error_class": "timeout"}) \
        == "shell|timeout"
    assert playbook.parse_section("shell|timeout") == \
        {"tool": "shell", "error_class": "timeout"}
    assert playbook.parse_section("shell") == {"tool": "shell", "error_class": "*"}
