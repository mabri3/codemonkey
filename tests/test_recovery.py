"""Cycle 90 (loop 39): recovery policy table + budget cap + typed report.

Report-only (C90): the policy advises on stuck, the budget verdict is
emitted, the run still completes. Termination is C91 (AWAITING-ASK).
"""

from __future__ import annotations

from codemonkey.recovery import (DEFAULT_RECOVERY_BUDGET, POLICY_TABLE,
                                 RecoveryTracker, consult, failure_report)


# ---------------- policy table ----------------

def test_wrong_argument_advises_retry():
    r = consult("edit_file", "schema_mismatch", "missing 'path'")
    assert r["taxonomy"] == "wrong-argument"
    assert r["action"] == "retry-differently"
    assert "arguments" in r["hint"]


def test_constraint_violation_reports():
    r = consult("shell", "auth", "denied by permission rule")
    assert r["taxonomy"] == "constraint-violation"
    assert r["action"] == "stop-and-report"


def test_junk_never_raises_and_stays_advisory():
    r = consult("", "", "")
    assert r["action"] in ("retry-differently", "stop-and-report")
    assert r["taxonomy"]  # always a label, never empty
    r2 = consult("shell", "tool-error", "exit 1\nboom")
    assert r2["action"] == "retry-differently"  # unmapped tool-error: one more try


def test_table_covers_all_mapped_categories():
    for cat in ("wrong-argument", "wrong-tool", "observation-failure",
                "recovery-failure", "looping-over-action",
                "constraint-violation", "unmapped"):
        assert cat in POLICY_TABLE
        action, hint = POLICY_TABLE[cat]
        assert action in ("retry-differently", "stop-and-report")
        assert hint  # every row names an untried alternative or report shape


# ---------------- budget tracker ----------------

def test_budget_counts_post_error_turns():
    t = RecoveryTracker(budget=8)
    assert t.post_error_turns(5) == 0  # no error yet: no budget consumed
    t.note_error(2)
    assert t.post_error_turns(2) == 0
    assert t.post_error_turns(9) == 7
    assert not t.exhausted(9)
    assert t.exhausted(10)  # 10 - 2 == budget
    assert t.budget == DEFAULT_RECOVERY_BUDGET == 8


def test_saved_math_reports_turns_and_tokens():
    t = RecoveryTracker(budget=8)
    saved = t.saved_vs_max_turns(30, 10, tokens_spent=200, turns_elapsed=10)
    assert saved == {"turns": 20, "tokens": 400}  # avg 20/tok × 20 turns
    zero = t.saved_vs_max_turns(30, 30, tokens_spent=0, turns_elapsed=0)
    assert zero == {"turns": 0, "tokens": 0}  # no div-by-zero, no negative


# ---------------- typed report ----------------

def test_failure_report_shape():
    r = failure_report(failure_class="tool-error", taxonomy="unmapped",
                       first_stuck_turn=3, attempts=1,
                       checkpoint_id="cp1", journal_thread="t1")
    assert r == {"type": "failure_report", "failure_class": "tool-error",
                 "taxonomy": "unmapped", "first_stuck_turn": 3, "attempts": 1,
                 "checkpoint_id": "cp1", "journal_thread": "t1"}


# ---------------- R-I: scripted failing run → trace ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


class FailProv:
    """Every turn: the same denied write (approval=never soft-denies it)."""

    protocol = "openai"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                    '{"path": "/tmp/cm90-denied.txt", "content": "x"}}\n')

    def close(self):
        pass


def test_failing_run_reports_first_stuck_and_would_have_saved(tmp_path, monkeypatch):
    import codemonkey.exec as exec_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    prov = FailProv()
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    code = exec_mod.run_exec(
        "Write x to /tmp/cm90-denied.txt", cwd=tmp_path,
        skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="", sandbox="workspace-write", approval="never",
        event_sink=events, max_turns=12)
    # report-only: the run COMPLETES (enforced stop is C91, AWAITING-ASK)
    assert code in (0, 1)
    consulted = [e for e in events if e.get("type") == "failure_report.consulted"]
    assert consulted, "no policy consult in trace"
    rep = consulted[0]["report"]
    assert rep["first_stuck_turn"] == 3  # streak ×3 fires on turn 3
    assert rep["journal_thread"]  # resume handle present
    exhausted = [e for e in events if e.get("type") == "failure_report.budget_exhausted"]
    assert exhausted, "no budget verdict in trace"
    last = exhausted[-1]
    # first error turn 1 + budget 8 → exhausted at turn 9 of 12:
    # would-have-saved 3 turns AND a token estimate (R-F: both, off the wire)
    assert last["would_save_turns"] == 3
    assert last["would_save_tokens"] > 0
    assert last["report"]["first_stuck_turn"] == 3
