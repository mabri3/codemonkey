"""R30: anytime-valid sequential certificates."""

from __future__ import annotations

from codemonkey.certify import m_certificate, sequential_verdict


def test_all_pass_certifies_true():
    flags = [True] * 20
    assert m_certificate(flags) is True


def test_all_fail_certifies_false():
    flags = [False] * 20
    assert m_certificate(flags) is False


def test_tied_undecided():
    assert m_certificate([True, False] * 10) is None
    assert m_certificate([True]) is None  # too few samples


def test_sequential_stops_early():
    outcomes = [True] * 6 + [False] * 2
    res = sequential_verdict(outcomes, min_n=2)
    assert res["certified_pass"] is True
    assert res["at_n"] == 6 and res["total"] == 8
    assert res["stopped_early"] is True


def test_undecided_no_certificate():
    res = sequential_verdict([True, False] * 5, min_n=2)
    assert res["certified_pass"] is None and not res["stopped_early"]


def test_all_fail_runs_false():
    res = sequential_verdict([False] * 20)
    assert res and res["certified_pass"] is False
