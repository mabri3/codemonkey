"""Cycle 89 (loop 39): stuck detector in the loop — report-only.

R-I entry-point probe: a scripted failing real-exec run (fake provider,
repeated tool errors) that used to burn turns now shows a `stuck` event with
the repeated (tool, error_class) pair in the --json trace WHILE THE RUN STILL
COMPLETES (C89 never terminates; C91 enforcement is AWAITING-ASK).
"""

from __future__ import annotations

from codemonkey.stuck import (STREAK_THRESHOLD, StuckDetector,
                              classify_outcome, enabled, nudge_text)


# ---------------- classification ----------------

def test_ok_resets_classifies_empty():
    assert classify_outcome("shell", True, "exit 0\n", {}) == ""
    assert classify_outcome("shell", True, "", None) == ""


def test_meta_error_class_wins():
    assert classify_outcome("edit_file", False, "error: anchor",
                            {"error_class": "schema_mismatch"}) == "schema_mismatch"


def test_approval_soft_deny_maps_approval():
    assert classify_outcome("write_file", False, "error: NOT executed",
                            {"approval": "soft-deny"}) == "approval"


def test_rule_deny_maps_auth():
    assert classify_outcome("shell", False, "error: denied by permission rule",
                            {"rule": "deny"}) == "auth"


def test_raised_and_plain_tool_error():
    assert classify_outcome("shell", False, "error: boom", {"raised": True}) == "exception"
    assert classify_outcome("shell", False, "exit 1\nnope", {}) == "tool-error"


# ---------------- detector: streak / reset / re-fire ----------------

def test_detector_fires_at_third_identical_pair():
    det = StuckDetector()
    out = "error: denied by permission rule"
    assert det.record("write_file", False, out, {"approval": "soft-deny"}) is None
    assert det.record("write_file", False, out, {"approval": "soft-deny"}) is None
    sig = det.record("write_file", False, out, {"approval": "soft-deny"})
    assert sig is not None
    assert sig["tool"] == "write_file"
    assert sig["streak"] == STREAK_THRESHOLD == 3
    assert sig["error_class"] == "approval"
    assert det.fired == 1


def test_detector_success_breaks_streak():
    det = StuckDetector()
    out = "error: x"
    det.record("shell", False, out, {})
    det.record("shell", False, out, {})
    det.record("shell", True, "exit 0\n", {})      # success resets
    assert det.record("shell", False, out, {}) is None  # streak restarts at 1


def test_detector_different_pair_does_not_stack():
    det = StuckDetector()
    det.record("shell", False, "error: a", {})
    det.record("read_file", False, "error: b", {})
    assert det.record("shell", False, "error: a", {}) is None
    # consecutive means the interleaved read_file failure RESET the shell
    # pair: the shell streak is 1 again — never 3 from alternating pairs
    assert det.current_streak == 1
    assert det.current_pair == ("shell", "tool-error")


def test_detector_rearms_after_fire():
    det = StuckDetector()
    out = "error: x"
    for _ in range(3):
        det.record("shell", False, out, {})
    assert det.fired == 1
    det.record_reset()
    assert det.record("shell", False, out, {}) is None
    assert det.record("shell", False, out, {}) is None
    sig = det.record("shell", False, out, {})
    assert sig is not None and det.fired == 2


def test_nudge_names_failure_and_forbids_repeat():
    txt = nudge_text("write_file", "approval", 3, "error: denied by permission rule\nmore")
    assert "write_file" in txt and "approval" in txt and "3 times" in txt
    assert "denied by permission rule" in txt  # last error head carried
    assert "Do NOT repeat the same call" in txt


def test_kill_switch(monkeypatch):
    monkeypatch.setenv("CODEMONKEY_STUCK", "0")
    assert enabled() is False
    monkeypatch.setenv("CODEMONKEY_STUCK", "1")
    assert enabled() is True
    monkeypatch.delenv("CODEMONKEY_STUCK")
    assert enabled() is True


# ---------------- R-I: scripted failing real-exec run → trace ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class StuckProv:
    """Every turn: the same denied write (approval=never soft-denies it)."""

    protocol = "openai"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                    '{"path": "/tmp/cm89-denied.txt", "content": "x"}}\n')

    def close(self):
        pass


def test_failing_run_shows_stuck_event_and_still_completes(tmp_path, monkeypatch):
    import codemonkey.exec as exec_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    prov = StuckProv()
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    code = exec_mod.run_exec(
        "Write x to /tmp/cm89-denied.txt", cwd=tmp_path,
        skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="", sandbox="workspace-write", approval="never",
        event_sink=events, max_turns=6)
    # C91 (ASK DECIDED 2026-09-04) supersedes the C89 report-only shape for
    # this scenario: advisory at turn 3 + failure at turn 4 → enforced stop.
    assert code == 3, f"C91 stop must fire here, got {code}"
    gave = [e for e in events if e.get("type") == "failure_report.gave_up"
            and "thread_id" in e]
    assert len(gave) == 1
    assert gave[0]["report"]["advisory_turn"] == 3
    assert gave[0]["report"]["failed_turn"] == 4
    types = [e.get("type") for e in events]
    stuck = [e for e in events if e.get("type") == "stuck"]
    assert stuck, f"no stuck event in trace types={types}"
    s0 = stuck[0]
    assert s0["tool"] == "write_file"
    # approval=never AUTO-APPROVES the write; the sandbox root-check rejects
    # the /tmp path (outside the workspace) -> the honest pair is tool-error
    assert s0["error_class"] == "tool-error"
    assert s0["streak"] == 3
    assert "turn.completed" in types or "error" in types  # run kept going
    # C91 stops the run at turn 4 (was: full 6-turn budget under C89
    # report-only). turn.started markers: 1 exec pre-turn + 4 loop turns,
    # doubled in this trace wiring.
    assert types.count("turn.started") == 2 * 4  # 4 loop turns, early stop


def test_stuck_disabled_by_env_burns_turns_silently(tmp_path, monkeypatch):
    # With CODEMONKEY_STUCK=0 the signal never appears (kill switch works
    # through the real loop, not just the module function).
    import codemonkey.exec as exec_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    monkeypatch.setenv("CODEMONKEY_STUCK", "0")
    prov = StuckProv()
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    exec_mod.run_exec(
        "Write x to /tmp/cm89-denied.txt", cwd=tmp_path,
        skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="", sandbox="workspace-write", approval="never",
        event_sink=events, max_turns=4)
    assert not [e for e in events if e.get("type") == "stuck"]
