"""Loop 43 acceptance — the live conformance probe, retired with a run behind it.

`build/conformance.py`'s `live_probe` was the suite's only BLOCKED row whenever
no model endpoint answered, which left contract §2's success-path types
(`item.*`, `turn.completed` usage) unverified on every machine without a box —
the same conflation 102F10 split for the A-sweep.

The probe is ENDPOINT-GATED: it drives the binary and asserts our loop's
output, and `build/stub_provider.py` speaks the API over real HTTP. So it is
retired here with a real run, not waived.

Break-verified: this fails if `live_probe` regresses (the stub run's exit code
is the driver's exit code), so §2's success-path coverage is now a control
rather than a promise.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "build" / "conformance_with_stub.py"


def test_live_probe_passes_against_a_scripted_endpoint():
    proc = subprocess.run([sys.executable, str(DRIVER)], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=300)
    out = proc.stdout
    assert proc.returncode == 0, (
        f"conformance went red against a scripted endpoint:\n{out}\n{proc.stderr}")
    assert "PASS live-exec" in out, (
        f"the live probe did not report PASS — §2's success-path types are "
        f"unverified again:\n{out}")
    assert "live PASS" in out


def test_the_scripted_endpoint_actually_served_the_run():
    """A green here must mean the binary talked to the stub, not that the
    probe silently skipped. The stub prints its address; the run must have
    produced events through it."""
    proc = subprocess.run([sys.executable, str(DRIVER)], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=300)
    assert "scripted endpoint: http://127.0.0.1:" in proc.stdout
    assert "PASS envelope (exit 0)" in proc.stdout
