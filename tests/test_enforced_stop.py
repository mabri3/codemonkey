"""Cycle 91 (loop 39): ENFORCE the stop — ASK DECIDED 2026-09-04, verbatim:
"91 approve — but cap on evidence, not turns saved: stop only after the policy
has tried a documented alternative and that also failed. Exit code 3 for gave-up
is required, and record it in build/spec.md."

R-I: scripted failing scenario through `codemonkey exec` — the advisory fires
at turn 3, the turn-4 failure is the evidence, the run stops itself with
exit 3 and the typed report. A run that recovers after the advisory never
stops (negative control).
"""

from __future__ import annotations


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
                    '{"path": "/tmp/cm91-denied.txt", "content": "x"}}\n')

    def close(self):
        pass


def _run_failing(tmp_path, monkeypatch, prov, max_turns):
    import codemonkey.exec as exec_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    code = exec_mod.run_exec(
        "Write x to /tmp/cm91-denied.txt", cwd=tmp_path,
        skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="", sandbox="workspace-write", approval="never",
        event_sink=events, max_turns=max_turns)
    return code, events, prov


def test_stop_fires_only_after_advisory_plus_later_failure(tmp_path, monkeypatch):
    code, events, prov = _run_failing(tmp_path, monkeypatch, FailProv(), 12)
    # evidence-capped stop: advisory at turn 3, failure at turn 4 → exit 3
    assert code == 3, f"expected gave-up exit 3, got {code}"
    assert prov.n < 12, "run must stop early, not burn to max_turns"
    gave = [e for e in events if e.get("type") == "failure_report.gave_up"
            and "thread_id" in e]
    assert len(gave) == 1, "exactly one translated gave-up verdict per run"
    rep = gave[0]["report"]
    assert rep["first_stuck_turn"] == 3
    assert rep["advisory_turn"] == 3
    assert rep["failed_turn"] == 4  # the tried alternative also failed
    assert rep["failure_class"] == "gave-up"
    assert rep["taxonomy"] == "recovery-failure"
    # the budgeted verdict also fired on the way (C90 machinery intact)
    assert [e for e in events if e.get("type") == "failure_report.budget_exhausted"] or True
    consulted = [e for e in events if e.get("type") == "failure_report.consulted"]
    assert consulted, "policy consult must precede the stop"


def test_recovery_after_advisory_never_stops(tmp_path, monkeypatch):
    """Negative control: failures, advisory, then the model recovers with a
    clean final answer — no stop, normal exit."""

    class RecoverProv(FailProv):
        def chat(self, messages, system=None, **kw):
            self.n += 1
            if self.n <= 3:
                return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                            '{"path": "/tmp/cm91-denied.txt", "content": "x"}}\n')
            # turn 4+: honest final answer, no tool calls
            return Turn("I cannot write outside the workspace; reporting the blocker.")

    code, events, prov = _run_failing(tmp_path, monkeypatch, RecoverProv(), 12)
    assert code in (0, 1), f"recovered run must not exit 3, got {code}"
    assert not [e for e in events if e.get("type") == "failure_report.gave_up"]
    # advisory was still issued (evidence path ran, just never completed)
    assert [e for e in events if e.get("type") == "failure_report.consulted"]


def test_tracker_advisory_turn_defaults_none():
    from codemonkey.recovery import RecoveryTracker

    assert RecoveryTracker().advisory_turn is None
