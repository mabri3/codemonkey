"""Cycle 93 (loop 40): repro-first gate — write-test → expect-FAIL →
allow-patch → expect-PASS. A patch with no observed pre-fail is UNVERIFIED.
"""

from __future__ import annotations

from codemonkey.loop import run_turns
from codemonkey.repro import ReproTracker, is_test_path
from codemonkey.sandbox import ToolContext


# ---------------- unit: classification ----------------

def test_is_test_path_conventions():
    assert is_test_path("tests/test_repro_gate.py")
    assert is_test_path("test_repro_gate.py")
    assert is_test_path("pkg/foo_test.py")
    assert is_test_path("test/unit/a.py")
    assert not is_test_path("src/codemonkey/loop.py")
    assert not is_test_path("README.md")
    assert not is_test_path("contest.py")  # 'test' inside a name is not a test


# ---------------- unit: state machine ----------------

def test_full_cycle_verifies():
    t = ReproTracker()
    t.note_write("tests/test_x.py")
    t.note_verify(False)
    t.note_write("src/x.py")
    t.note_verify(True)
    assert t.verdict() == "VERIFIED"
    rep = t.report()
    assert rep["transitions"] == [
        "test-written:tests/test_x.py", "fail-observed",
        "patched:src/x.py", "pass-observed"]
    assert rep["reason"] == ""


def test_pass_without_fail_is_unverified():
    t = ReproTracker()
    t.note_write("tests/test_x.py")
    t.note_write("src/x.py")
    t.note_verify(True)
    assert t.verdict() == "UNVERIFIED"
    assert "never observed" in t.report()["reason"]


def test_fail_without_test_does_not_count():
    t = ReproTracker()
    t.note_verify(False)  # strict: no test written → not a repro failure
    assert not t.fail_observed
    assert t.verdict() == "UNVERIFIED"
    assert "no reproduction test" in t.report()["reason"]


def test_new_test_restarts_cycle():
    t = ReproTracker()
    t.note_write("tests/test_a.py")
    t.note_verify(False)
    t.note_write("tests/test_b.py")  # fresh repro: old fail belongs to test_a
    assert not t.fail_observed and not t.patched
    assert t.verdict() == "UNVERIFIED"


def test_report_shape():
    rep = ReproTracker().report()
    assert rep == {"type": "repro.verdict", "verdict": "UNVERIFIED",
                   "test_written": False, "fail_observed": False,
                   "patched": False, "pass_observed": False,
                   "reason": "no reproduction test was written",
                   "transitions": []}


# ---------------- R-I: scripted fix run through the real loop ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


class FixProv:
    """Turn 1: write the repro test. Turn 2: write the fix marker.
    Turn 3: final answer."""

    protocol = "openai"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                        '{"path": "tests/test_cm93.py", "content": "x"}}\n')
        if self.n == 2:
            return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                        '{"path": "fixed.marker", "content": "fixed"}}\n')
        return Turn("fixed and verified")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=30)


def test_fix_run_counts_verified(tmp_path):
    prov = FixProv()
    events: list = []
    turn = run_turns(
        prov, "fix it", _ctx(tmp_path), tool_protocol="prompt", max_turns=8,
        verify_command=f'test -f "{tmp_path}/fixed.marker"',
        max_verify_retries=3,  # turn 1's expected failure consumes one retry
        on_event=events.append)
    verdicts = [e for e in events if e.get("type") == "repro.verdict"]
    assert verdicts, "no repro verdict on the trace"
    rep = verdicts[-1]["report"]
    assert rep["verdict"] == "VERIFIED", rep
    assert rep["test_written"] and rep["fail_observed"]
    assert rep["patched"] and rep["pass_observed"]
    assert getattr(turn, "repro", {}).get("verdict") == "VERIFIED"


def test_prefixed_run_is_unverified(tmp_path):
    (tmp_path / "fixed.marker").write_text("already fixed")
    prov = FixProv()
    events: list = []
    run_turns(
        prov, "fix it", _ctx(tmp_path), tool_protocol="prompt", max_turns=8,
        verify_command=f'test -f "{tmp_path}/fixed.marker"',
        on_event=events.append)
    verdicts = [e for e in events if e.get("type") == "repro.verdict"]
    assert verdicts
    rep = verdicts[-1]["report"]
    assert rep["verdict"] == "UNVERIFIED", rep
    assert "never observed" in rep["reason"]
