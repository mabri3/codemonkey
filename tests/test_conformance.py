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
    assert len(results) == 7 and all(r["ok"] for r in results)


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
