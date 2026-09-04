"""R30 certificates, R-H renamed (loop 38, cycle 77): the fixed-n Hoeffding
bound is `hoeffding_gate` (verdicts carry kind "hoeffding-gate");
`sequential_verdict` is a deprecated alias kept one release."""

from __future__ import annotations

import warnings

from codemonkey.certify import hoeffding_gate, m_certificate, sequential_verdict


def test_all_pass_certifies_true():
    flags = [True] * 20
    assert m_certificate(flags) is True


def test_all_fail_certifies_false():
    flags = [False] * 20
    assert m_certificate(flags) is False


def test_tied_undecided():
    assert m_certificate([True, False] * 10) is None
    assert m_certificate([True]) is None  # too few samples


def test_gate_carries_kind():
    res = hoeffding_gate([True] * 6 + [False] * 2)
    assert res["kind"] == "hoeffding-gate"
    assert res["certified_pass"] is True
    assert res["at_n"] == 6 and res["total"] == 8
    assert res["stopped_early"] is True


def test_gate_undecided_carries_kind():
    res = hoeffding_gate([True, False] * 5)
    assert res["kind"] == "hoeffding-gate"
    assert res["certified_pass"] is None and not res["stopped_early"]


def test_gate_all_fail():
    res = hoeffding_gate([False] * 20)
    assert res["kind"] == "hoeffding-gate"
    assert res and res["certified_pass"] is False


def test_old_name_warns_but_still_works():
    outcomes = [True] * 6 + [False] * 2
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        res = sequential_verdict(outcomes, min_n=2)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert "hoeffding_gate" in str(caught[0].message)
    assert res == hoeffding_gate(outcomes, min_n=2)
