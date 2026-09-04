"""Cycle 52 (loop17): honest-completion gate (verify_claims)."""

from __future__ import annotations

import pytest

from codemonkey.claims import annotate, check_claims
from codemonkey.journal import record


@pytest.fixture()
def chome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_file_claim_exists_verified(chome):
    (chome / "out.txt").write_text("x")
    res = check_claims("I created the file `out.txt` with the data.",
                       workdir=chome, thread_id="t")
    assert res["verified"] == [{"kind": "file", "target": "out.txt"}]
    assert res["unverified"] == []


def test_file_claim_missing_unverified(chome):
    res = check_claims("I created the file `ghost.py`.",
                       workdir=chome, thread_id="t")
    assert res["unverified"] == [{"kind": "file", "target": "ghost.py"}]


def test_command_claim_with_journal_evidence(chome):
    record("tc", "intent", tool="shell", key="k", status="ok",
           output="pytest test_x.py: 1 passed")
    res = check_claims("Ran the tests and they pass.",
                       workdir=chome, thread_id="tc")
    assert res["verified"], res


def test_command_claim_without_evidence(chome):
    res = check_claims("Ran the command `scripts/deploy.sh` successfully.",
                       workdir=chome, thread_id="t-empty")
    assert res["unverified"]


def test_annotate_appends_marker_and_journals(chome):
    reply, res = annotate("I created the file `missing.txt`.",
                          workdir=chome, thread_id="ta")
    assert "[UNVERIFIED:" in reply
    assert res["unverified"]
    from codemonkey.journal import read_thread, class_summary
    assert any(r.get("tool") == "verify_claims" for r in read_thread("ta"))


def test_clean_reply_untouched(chome):
    (chome / "real.txt").write_text("x")
    reply, res = annotate("I created the file `real.txt`.",
                          workdir=chome, thread_id="tb")
    assert "[UNVERIFIED" not in reply
    assert res["unverified"] == []


def test_reply_without_claims_noop(chome):
    reply, res = annotate("The weather is nice.", workdir=chome, thread_id="tc2")
    assert reply == "The weather is nice."
    assert res["claims"] == []
