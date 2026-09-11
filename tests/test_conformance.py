"""Cycle 102 (loop 43): conformance suite over the released binary.

The charter probe (independent process, docs-only knowledge, green on the
binary, deliberate schema break FAILS) is this file plus
build/conformance.py. Live end-to-end stays endpoint-gated: BLOCKED with
reason while .176 refuses connections.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from pathlib import Path
import importlib.util


def _driver():
    path = Path(__file__).parent.parent / "build" / "conformance.py"
    spec = importlib.util.spec_from_file_location("cm_conformance", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_drv = _driver()
ConformanceFailure = _drv.ConformanceFailure
check_envelope = _drv.check_envelope
check_stream = _drv.check_stream
offline_probes = _drv.offline_probes
run_binary = _drv.run_binary


def test_envelope_validator_accepts_v1():
    ev = check_envelope({"v": 1, "type": "turn.completed"})
    assert ev["type"] == "turn.completed"


def test_envelope_missing_v_fails():
    with pytest.raises(ConformanceFailure, match="missing v"):
        check_envelope({"type": "turn.completed"})


def test_envelope_unknown_v_fails():
    with pytest.raises(ConformanceFailure, match="unknown envelope"):
        check_envelope({"v": 99, "type": "turn.completed"})


def test_deliberate_schema_break_fails_stream():
    # The charter's negative control: strip v from one line of a valid
    # stream → the suite FAILS (detects), it must never pass silently.
    good = json.dumps({"v": 1, "type": "thread.started", "thread_id": "t"})
    broken = json.dumps({"type": "turn.completed"})
    with pytest.raises(ConformanceFailure):
        check_stream(good + "\n" + broken + "\n")


def test_offline_probes_green_on_binary(tmp_path):
    results = offline_probes(tmp_path)
    assert len(results) == 8 and all(r["ok"] for r in results)


def test_envelope_probe_reads_a_real_stream_from_the_binary(tmp_path):
    """102F1 regression: the envelope gate must be applied to events the
    BINARY emitted. The shipped C102 suite asserted only on dicts written
    by hand, so a binary with `events.stamp` deleted stayed 7/7 green —
    the deliberate-break control could not detect the deliberate break.

    No endpoint is needed: an unreachable one still drives thread.started /
    turn.started / error through the exec funnel, and contract §2 binds
    every event crossing it.
    """
    out = _drv.envelope_probe(tmp_path)
    assert out["status"] == "PASS", out.get("reason")
    assert out["events"] >= 2, out


def test_envelope_probe_fails_a_binary_that_drops_v(tmp_path, monkeypatch):
    """The control, exercised: a binary whose stream lacks `v` FAILS."""

    class _Proc:
        returncode = 1
        stdout = ('{"type": "thread.started", "thread_id": "t"}\n'
                  '{"type": "error", "message": "x"}\n')
        stderr = ""

    monkeypatch.setattr(_drv, "run_binary", lambda *a, **k: _Proc())
    with pytest.raises(ConformanceFailure, match="missing v"):
        _drv.envelope_probe(tmp_path)


def test_envelope_probe_rejects_an_empty_stream(tmp_path, monkeypatch):
    """Contract §3: --json stdout carries the stream. Silence is a failure,
    not a pass — except exit 2, which is 'no provider here' (BLOCKED)."""

    class _Proc:
        returncode = 1
        stdout = "   \n"
        stderr = "boom"

    monkeypatch.setattr(_drv, "run_binary", lambda *a, **k: _Proc())
    with pytest.raises(ConformanceFailure, match="empty event stream"):
        _drv.envelope_probe(tmp_path)

    class _Usage(_Proc):
        returncode = 2

    monkeypatch.setattr(_drv, "run_binary", lambda *a, **k: _Usage())
    out = _drv.envelope_probe(tmp_path)
    assert out["status"] == "BLOCKED" and out["reason"]


def test_live_exec_blocked_or_versioned(tmp_path):
    live_probe = _drv.live_probe

    out = live_probe(tmp_path)
    assert out["status"] in ("PASS", "BLOCKED")
    if out["status"] == "PASS":
        assert out["events"] > 0
    else:
        assert out["reason"], "BLOCKED without a reason is silence"


def test_binary_addressable_docs_only():
    # No repo imports were needed to reach the binary: this file imports
    # only the doc-derived driver. The probe below uses --help text alone.
    proc = run_binary("--help")
    assert proc.returncode == 0 and "exec" in proc.stdout


def test_type_coverage_enumerates_contract(tmp_path):
    """102F7/102F8: the §2 list — PARSED FROM THE DOCUMENT — is enumerated
    against streams the binary produced, and every documented wire type is
    accounted for."""
    cov = _drv.type_coverage(tmp_path)
    assert cov["ok"], cov
    assert cov["covered"] == cov["documented"]["wire"], cov


def test_the_contract_lists_are_parsed_not_copied():
    """102F8: `build/contract.md` §2 is the source of truth.

    This replaces a test that iterated over a hand-maintained copy of the list
    in `conformance.py` and checked only code -> doc. A type added to §2 with
    nothing producing it was invisible — demonstrated on HEAD by adding
    `checkpoint.created` to §2 and watching the suite stay green. The parser
    now reads the marked regions, so the document drives the control.
    """
    from pathlib import Path as _P

    doc_text = (_P(__file__).parent.parent / "build" / "contract.md").read_text()
    wire, internal = _drv.parse_contract_types()
    for t in sorted(wire):
        assert f"`{t}`" in doc_text, t
    for t in sorted(internal):
        assert f"`{t}`" in doc_text, t
    # the markers are load-bearing: without them the parser refuses to run
    assert _drv.WIRE_BEGIN in doc_text and _drv.WIRE_END in doc_text
    assert _drv.INTERNAL_BEGIN in doc_text and _drv.INTERNAL_END in doc_text


def test_contract_type_counts_are_pinned():
    """The exact counts, so a change to a BINDING document is deliberate.

    Adding a type here means adding a run that produces it; removing one is a
    major bump under §2's own compatibility rule. The runtime floor in
    `parse_contract_types` guards the other failure — a parse that matches
    nothing must never read as "all covered", which is this same bug one level
    down.
    """
    wire, internal = _drv.parse_contract_types()
    assert len(wire) == 18, sorted(wire)
    assert len(internal) == 2, sorted(internal)


def test_the_budget_pair_is_disambiguated_in_the_contract():
    """102F8: two events one character apart, with different producers and
    different effects, are spelled out in the binding document and their
    payloads are asserted disjoint by the coverage probe."""
    from pathlib import Path as _P

    doc = (_P(__file__).parent.parent / "build" / "contract.md").read_text()
    assert "disambiguation (102F8)" in doc
    assert "report only" in doc, "the recovery event's effect must be stated"
    assert "halts the run" in doc, "the declared-budget event's effect must be stated"
    assert "neither type is renamed" in doc.lower()


def test_run_binary_closes_stdin(monkeypatch):
    """102F2: `exec` with no prompt reads stdin. The driver inherited the
    parent's, so with an open-but-idle stdin (CI, a background runner) the
    exec-no-prompt probe blocked to the 120s timeout instead of observing
    exit 2 — the suite's verdict depended on its caller, not the binary.
    Reproduced with os.pipe() as stdin: HUNG at 15s; DEVNULL: exit 2 in 0.1s.
    """
    seen = {}

    def _fake_run(cmd, **kw):
        seen.update(kw)

        class _P:
            returncode = 0
            stdout = ""
            stderr = ""

        return _P()

    monkeypatch.setattr(_drv.subprocess, "run", _fake_run)
    _drv.run_binary("--version")
    assert seen.get("stdin") is subprocess.DEVNULL
