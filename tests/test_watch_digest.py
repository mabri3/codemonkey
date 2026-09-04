"""Loop 25 (cycle 62): status --watch + digest --last."""

from __future__ import annotations

import pytest

from codemonkey.digest import build_digest, digest_recent, render_multi
from codemonkey.journal import record
from codemonkey.status_mod import collect_latest_sessions, render_frame


@pytest.fixture()
def whome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_render_frame_pure(whome):
    data = {"jobs": {"count": 0, "items": []}, "journal": {"classes": {}},
            "sessions": {"count": 0}, "eval": {"baseline": None},
            "cost": {"runs": 0, "total_tokens": 0, "total_turns": 0},
            "spill": {"files": 0, "bytes": 0}}
    f1 = render_frame(data, 1)
    assert "jobs: none" in f1 and "cost ledger:" in f1
    # contains a timestamp line (HH:MM:SS)
    first = f1.splitlines()[0]
    assert len(first.split(":")) == 3


def test_digest_recent_ordering(whome):
    record("t-a", "intent", tool="shell", key="k1", status="ok")
    import time as _t
    _t.sleep(0.02)
    record("t-b", "intent", tool="shell", key="k2", status="ok")
    recs = digest_recent(2)
    assert recs[0]["thread"] == "t-b"  # newest first
    assert recs[1]["thread"] == "t-a"


def test_digest_recent_empty(whome):
    assert digest_recent(3) == []
    assert render_multi([]) == "(no threads)"


def test_render_multi_sections(whome):
    record("t1", "intent", tool="shell", key="k", status="ok")
    record("t2", "intent", tool="shell", key="k", status="ok")
    text = render_multi(digest_recent(2))
    assert text.count("# run digest:") == 2
    assert "\n\n---\n\n" in text


def test_collect_latest_sessions_newest_first(whome):
    from codemonkey.journal import journal_path
    # journal files double as session-ish artifacts for ordering check
    record("s-old", "intent", tool="shell", key="k", status="ok")
    import time as _t
    _t.sleep(0.02)
    record("s-new", "intent", tool="shell", key="k", status="ok")
    ids = collect_latest_sessions(2)
    assert ids == ["s-new", "s-old"]
