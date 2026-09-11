"""loop47 cycle 111 — the migration: lessons DELETED INTO the playbook,
parity-gated.

The load-bearing claims:

* every previously-verified lesson is retrievable from the playbook after the
  migration (the parity gate, two-way — a drop refuses AND rolls back);
* the verified flag carries over as `admitted`; drafts stay quarantined;
* tags {tool, error_class} round-trip through the section encoding, so
  `retrieve`'s scoring is unchanged;
* the OLD FILE IS ARCHIVED, not destroyed, and stays in place when parity
  fails;
* the discriminating negative: when a migration silently drops an entry, the
  gate must catch it (missing → rollback) — the test plants exactly that drop
  via monkeypatch and watches the run abort byte-identically.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from codemonkey import playbook
from codemonkey.lessons import load_all, retrieve


def _lessons_file(tmp_path, entries) -> Path:
    p = tmp_path / "lessons.json"
    p.write_text(json.dumps(entries))
    return p


LESSONS = [
    {"id": "les-1-1", "tags": {"tool": "shell", "error_class": "timeout"},
     "text": "use streaming deadlines for shell", "verified": True,
     "created": 1.0},
    {"id": "les-1-2", "tags": {"tool": "repo_map", "error_class": "parse"},
     "text": "repo_map chokes on generated dirs", "verified": True,
     "created": 2.0},
    {"id": "les-1-3", "tags": {"tool": "*", "error_class": "*"},
     "text": "draft: revisit retry policy", "verified": False, "created": 3.0},
]


def _migrate(tmp_path, monkeypatch, entries=None):
    ws = tmp_path / "ws"
    ws.mkdir()
    lf = _lessons_file(tmp_path, entries or LESSONS)
    monkeypatch.chdir(ws)
    rep = playbook.migrate_lessons(ws, lesson_file=lf)
    return ws, lf, rep


def test_migration_parity_and_archive(tmp_path, monkeypatch):
    ws, lf, rep = _migrate(tmp_path, monkeypatch)
    assert rep["migrated"] == 3 and rep["verified"] == 2
    assert rep["archived"]
    assert not lf.exists() and Path(rep["archived"]).exists()  # archived, not burned

    # verified -> admitted; draft -> quarantined
    rows = {e["text"]: e for e in playbook.list_entries(ws) if e["kind"] == "lesson"}
    assert rows["use streaming deadlines for shell"]["status"] == "admitted"
    assert rows["repo_map chokes on generated dirs"]["status"] == "admitted"
    assert rows["draft: revisit retry policy"]["status"] == "quarantined"

    # legacy surface still answers, with the same texts and tags
    legacy = {e["text"]: e for e in load_all(ws)}
    assert set(legacy) == {e["text"] for e in LESSONS}
    assert legacy["use streaming deadlines for shell"]["tags"] == \
        {"tool": "shell", "error_class": "timeout"}

    # retrieval parity on the same task text (scoring unchanged)
    hits = retrieve("shell timeout issue", )
    # (retrieve reads cwd — which the fixture chdir'd to the workspace)


def test_retrieval_parity_on_real_tasks(tmp_path, monkeypatch):
    ws, lf, rep = _migrate(tmp_path, monkeypatch)
    hits = retrieve("shell timeout on big output")
    assert [h["text"] for h in hits] == ["use streaming deadlines for shell"]
    assert retrieve("repo_map parse failure")[0]["text"] == \
        "repo_map chokes on generated dirs"
    assert retrieve("completely different") == []
    # draft is not retrievable even though it is in the store
    assert all("draft" not in h["text"] for h in retrieve("retry policy"))


def test_parity_gate_refuses_a_dropped_entry_and_rolls_back(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    lf = _lessons_file(tmp_path, LESSONS)
    monkeypatch.chdir(ws)
    # plant a pre-existing entry so the rollback is byte-checkable
    playbook.merge_deltas(ws, [{
        "kind": "strategy", "section": "tools", "text": "pre-existing",
        "provenance": {"run_id": "r", "session_id": "", "taint_free": True}}])
    before = playbook.store_path(ws).read_bytes()

    real_merge = playbook.merge_deltas

    def dropping_merge(workdir, deltas):
        # simulate a migration bug: the VERIFIED entry's delta never lands
        keep = [d for d in deltas
                if d["text"] != "repo_map chokes on generated dirs"]
        return real_merge(workdir, keep)

    monkeypatch.setattr(playbook, "merge_deltas", dropping_merge)
    with pytest.raises(playbook.PlaybookError) as ei:
        playbook.migrate_lessons(ws, lesson_file=lf)
    assert "parity gate FAILED" in str(ei.value)
    assert "missing" in str(ei.value)
    monkeypatch.setattr(playbook, "merge_deltas", real_merge)

    # rolled back byte-identically; the lessons file was NOT touched
    assert playbook.store_path(ws).read_bytes() == before
    assert lf.exists()


def test_parity_gate_also_refuses_a_dropped_draft(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    lf = _lessons_file(tmp_path, LESSONS)
    monkeypatch.chdir(ws)
    real_merge = playbook.merge_deltas

    def drop_draft(workdir, deltas):
        keep = [d for d in deltas if not d["text"].startswith("draft:")]
        return real_merge(workdir, keep)

    monkeypatch.setattr(playbook, "merge_deltas", drop_draft)
    with pytest.raises(playbook.PlaybookError) as ei:
        playbook.migrate_lessons(ws, lesson_file=lf)
    assert "drafts dropped" in str(ei.value)
    monkeypatch.setattr(playbook, "merge_deltas", real_merge)
    assert lf.exists()


def test_missing_lessons_file_is_honest(tmp_path, monkeypatch):
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    rep = playbook.migrate_lessons(ws, lesson_file=tmp_path / "nope.json")
    assert rep["migrated"] == 0 and "no lessons file" in rep["reason"]


def test_real_home_file_is_not_touched_by_tests(tmp_path, monkeypatch):
    # the default path is ~/.codemonkey/lessons.json — tests must pass
    # lesson_file explicitly; this pins that the default is HOME-based
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    rep = playbook.migrate_lessons(ws)   # no lesson_file -> HOME default
    assert rep["migrated"] == 0
    assert ".codemonkey/lessons.json" in rep["reason"]
