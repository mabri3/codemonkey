"""loop45 cycle 105 — the evidence pack, and what breaks it.

The pack exists because a claim and its evidence stored together are worth
little. These tests attack the pack the way a reader should: edit a record,
delete one, reorder two, carry it to a journal that has moved on, and put a
secret in a journaled command.

Break-verified the R-I way: `evidence.py`'s `link()` was changed to hash only
the record (dropping the previous link), which makes the chain a per-record
digest that still verifies internally — the tests below go RED because a
reordered pack then reproduces the same head. See BUILD_LOG for the exact
failure text.
"""

from __future__ import annotations

import copy
import json

import pytest

from codemonkey import evidence as ev


def _records() -> list[dict]:
    return [
        {"ts": 1.0, "type": "call", "thread": "t1", "tool": "shell",
         "key": "k1", "status": "ok", "command": "echo hi"},
        {"ts": 2.0, "type": "outcome", "thread": "t1", "tool": "shell",
         "key": "k1", "status": "ok", "output": "hi"},
        {"ts": 3.0, "type": "call", "thread": "t1", "tool": "write_file",
         "key": "k2", "status": "ok", "command": "write a.txt"},
    ]


def _pack(records=None) -> dict:
    recs = records if records is not None else _records()
    chain = ev.build_chain(recs)
    return {"pack_version": 1, "thread_id": "t1", "records": recs,
            "chain": chain, "head": chain[-1] if chain else ev.GENESIS,
            "claims": ev.claims_from(recs), "counts": {"records": len(recs)}}


# ── the chain ──────────────────────────────────────────────────────────────

def test_an_untouched_pack_verifies():
    r = ev.verify(_pack())
    assert r["ok"] and r["internal"]


def test_editing_one_record_breaks_the_chain():
    doc = _pack()
    doc["records"][1]["output"] = "tampered"
    r = ev.verify(doc)
    assert not r["ok"] and not r["internal"]
    assert any("chain broken" in p for p in r["problems"])


def test_deleting_a_record_breaks_the_chain():
    doc = _pack()
    doc["records"].pop(1)
    r = ev.verify(doc)
    assert not r["ok"]
    assert any("added or removed" in p for p in r["problems"])


def test_reordering_records_breaks_the_chain():
    """A per-record digest would still verify after a reorder; a CHAIN must
    not. This is the test the break-run turns red."""
    doc = _pack()
    doc["records"][0], doc["records"][1] = doc["records"][1], doc["records"][0]
    assert not ev.verify(doc)["ok"]


def test_a_forged_head_is_caught():
    doc = _pack()
    doc["head"] = "0" * 64
    r = ev.verify(doc)
    assert not r["ok"]
    assert any("head does not match" in p for p in r["problems"])


def test_verification_against_the_live_journal_detects_drift():
    doc = _pack()
    assert ev.verify(doc, _records())["journal"] is True
    extended = _records() + [{"ts": 4.0, "type": "call", "thread": "t1",
                              "tool": "shell", "key": "k3", "status": "ok"}]
    r = ev.verify(doc, extended)
    assert not r["ok"] and r["journal"] is False
    assert any("journal on disk" in p for p in r["problems"])


def test_the_two_checks_are_independent():
    """A pack can be internally consistent AND stale. Reporting one number
    would hide that, so verify() reports both."""
    doc = _pack()
    doc["chain"][-1] = "f" * 64           # internally broken
    doc["head"] = "f" * 64
    r = ev.verify(doc, _records())
    assert r["internal"] is False
    assert r["journal"] is False


# ── redaction and claims ───────────────────────────────────────────────────

def test_secrets_are_redacted_before_they_are_hashed(monkeypatch, tmp_path):
    """The pack is a document meant to be handed to someone else."""
    from codemonkey import journal as journal_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    journal_mod.record("t-secret", "call", tool="shell", key="k",
                       output="curl -H 'Authorization: Bearer sk-abc123XYZ' x")
    doc = ev.pack("t-secret", needles=["sk-abc123XYZ"])
    blob = json.dumps(doc)
    assert "sk-abc123XYZ" not in blob, "a secret was sealed into the pack"
    assert doc["redactions"] >= 1


def test_every_claim_cites_the_records_it_rests_on():
    doc = _pack()
    assert doc["claims"]
    for c in doc["claims"]:
        assert c["evidence"], "a claim with no evidence is a bare assertion"
        assert all(0 <= i < len(doc["records"]) for i in c["evidence"])


def test_a_thread_with_no_journal_is_an_error_not_an_empty_pack(monkeypatch,
                                                                tmp_path):
    """An empty pack for a run that never happened would be a claim about
    nothing."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(FileNotFoundError):
        ev.pack("no-such-thread")


def test_the_pack_round_trips_through_json(monkeypatch, tmp_path):
    from codemonkey import journal as journal_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    journal_mod.record("t2", "call", tool="write_file", key="k",
                       output="wrote 3 bytes to a.txt")
    doc = ev.pack("t2")
    again = json.loads(json.dumps(doc))
    assert ev.verify(again)["ok"], "the pack does not survive serialization"


def test_render_names_the_head_and_the_claims():
    text = ev.render(_pack())
    assert "evidence pack v1" in text
    assert "claims" in text
    assert _pack()["head"][:16] in text


def test_canonical_is_key_order_independent():
    a = {"x": 1, "y": 2}
    b = {"y": 2, "x": 1}
    assert ev.canonical(a) == ev.canonical(b)


def test_chain_is_sensitive_to_a_single_character():
    doc = _pack()
    other = copy.deepcopy(doc)
    other["records"][0]["command"] = "echo hi."
    assert ev.build_chain(other["records"]) != doc["chain"]


def test_the_head_commits_to_every_record_not_just_the_last():
    """The property that makes this a CHAIN rather than a per-record digest.

    With independent digests the head is just a hash of the LAST record, so a
    pack whose earlier records were rewritten still quotes the same head — and
    the head is the thing anyone cites. A chain head changes when ANY record
    changes.

    (This test exists because the first break-run of this cycle was VOID: the
    suite passed with `link()` hashing the record alone. Reordering was still
    caught by positional comparison, so nothing pinned the chaining itself.)
    """
    doc = _pack()
    other = copy.deepcopy(doc)
    other["records"][0]["command"] = "echo a different command entirely"
    assert ev.build_chain(other["records"])[-1] != doc["chain"][-1], (
        "the head did not change when an EARLIER record changed — the pack "
        "head commits only to the last record, so an edited pack would still "
        "be quoted by the same head")


def test_a_pack_whose_earlier_record_was_rewritten_fails_verification():
    """The same defect, at the level a reader cares about: edit an early
    record, leave the head alone, and verification must fail."""
    doc = _pack()
    doc["records"][0]["command"] = "echo a different command entirely"
    assert not ev.verify(doc)["ok"]
