"""Cycle 45 (loop13): lessons store + extraction + scoped retrieval."""

from __future__ import annotations

import pytest

from codemonkey.lessons import (add, extract_drafts, lessons_path, load_all,
                                mark_verified, retrieve)


@pytest.fixture()
def lhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_add_and_load(lhome):
    e = add("prefer streaming with a deadline", tool="shell", error_class="timeout")
    all_ = load_all()
    assert len(all_) == 1 and all_[0]["text"] == e["text"]
    assert e["verified"] is False


def test_extract_drafts_from_journal_classes(lhome):
    drafts = extract_drafts({"timeout": 5, "ok": 10, "parse": 1}, threshold=2)
    assert len(drafts) == 1
    assert drafts[0]["tags"]["error_class"] == "timeout"
    assert drafts[0]["verified"] is False  # draft, not trusted


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


def test_atomic_writes(lhome):
    add("first", verified=True)
    p = lessons_path()
    p.with_suffix(".tmp").write_text("garbage")
    add("second", verified=True)
    assert len(load_all()) == 2


def test_mark_verified_roundtrip(lhome):
    e = add("lesson", tool="shell", error_class="timeout")
    assert mark_verified(e["id"])["verified"] is True
    assert load_all()[0]["verified"] is True
    assert mark_verified(e["id"], verified=False)["verified"] is False
    assert mark_verified("nope") is None
