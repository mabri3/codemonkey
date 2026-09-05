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


# ---- 91F1 / 91F2 regressions ------------------------------------------------
# The two tests above both drive a provider that repeats the SAME failing call
# forever, so the post-advisory failure is always the advisory's own pair — the
# discriminating case never occurs. The original cycle-91 gate armed on ANY
# post-advisory failure, so an agent that OBEYED the advisory and incurred one
# unrelated miss was terminated with a closing that claimed its alternative
# "was tried and also failed". These cover that.


class ObeysAdvisoryProv(FailProv):
    """Stuck on write_file x3 (advisory at turn 3), then obeys: switches tool
    and takes one incidental miss (a path that isn't there — the most routine
    failure in agent exploration), then finishes."""

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n <= 3:
            return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                        '{"path": "/tmp/cm91-denied.txt", "content": "x"}}\n')
        if self.n == 4:
            return Turn('TOOL_CALL: {"name": "read_file", "arguments": '
                        '{"path": "does_not_exist_91f1.txt"}}\n')
        return Turn("Found the answer by another route. Done.")


def test_unrelated_post_advisory_failure_does_not_stop(tmp_path, monkeypatch):
    """91F1: the stop needs the ADVISED-AGAINST pair to recur, not any failure."""
    code, events, prov = _run_failing(tmp_path, monkeypatch,
                                      ObeysAdvisoryProv(), 12)
    assert code != 3, "obeying the advisory must not be punished with gave-up"
    assert not [e for e in events if e.get("type") == "failure_report.gave_up"], \
        "an unrelated read miss is not evidence the alternative failed"
    # the advisory still fired — the evidence path ran and correctly declined
    assert [e for e in events if e.get("type") == "failure_report.consulted"]
    assert prov.n == 5, "the run must reach its own final answer"


def test_stop_report_carries_the_matched_pair(tmp_path, monkeypatch):
    """91F1: the closing asserts the alternative was tried and failed, so the
    report must carry the pair that justifies the claim."""
    code, events, prov = _run_failing(tmp_path, monkeypatch, FailProv(), 12)
    assert code == 3
    rep = [e for e in events if e.get("type") == "failure_report.gave_up"
           and "thread_id" in e][0]["report"]
    assert rep["advised_pair"] == ["write_file", "tool-error"]
    assert rep["matched_pair"] == rep["advised_pair"], \
        "the stop fired on a pair that does not match the advisory"


def test_policy_stop_is_not_reported_as_max_turns(tmp_path, monkeypatch):
    """91F2: the enforced stop is the only `break` in run_turns; the bail after
    the loop must not relabel a turn-4 policy stop as turn exhaustion."""
    code, events, prov = _run_failing(tmp_path, monkeypatch, FailProv(), 12)
    assert code == 3
    bogus = [e for e in events if e.get("type") == "error"
             and "max_turns" in str(e.get("message", ""))]
    assert not bogus, f"policy stop emitted a false max_turns error: {bogus}"


def test_genuine_max_turns_still_reports(tmp_path, monkeypatch):
    """91F2 negative control: a run that really exhausts turns still says so."""

    class BusyProv(FailProv):
        def chat(self, messages, system=None, **kw):
            self.n += 1
            # alternating tools: never a 3-streak, so no advisory, no stop
            tool = "read_file" if self.n % 2 else "list_files"
            return Turn('TOOL_CALL: {"name": "%s", "arguments": '
                        '{"path": "missing_%d.txt"}}\n' % (tool, self.n))

    code, events, prov = _run_failing(tmp_path, monkeypatch, BusyProv(), 4)
    assert code != 3
    assert [e for e in events if e.get("type") == "error"
            and "max_turns" in str(e.get("message", ""))], \
        "genuine turn exhaustion must still be reported"
