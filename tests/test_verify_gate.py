"""Cycle 19 (loop4): verify gate — verification inside the loop.

Verify probe (plan.md): >=5 tests — unset command never runs; failing command
feeds failure text + corrective turn; passing command adds no extra turn;
max_verify_retries respected; verify output charged to the observation budget;
events emitted in order.
"""

from __future__ import annotations

from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class WriteThenDone:
    """Turn 1: write a file (mutating). Turn 2: final."""

    def __init__(self):
        self.calls = 0
        self.seen = []

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.calls += 1
        self.seen.append(list(messages))
        if self.calls == 1:
            return Turn('TOOL_CALL: {"name": "write_file", "arguments": {"path": "out.txt", "content": "x"}}')
        return Turn("done")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=30)


def test_unset_command_never_runs(tmp_path):
    prov = WriteThenDone()
    events = []
    run_turns(prov, "write", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=4, verify_command=None, on_event=events.append)
    assert not [e for e in events if e.get("type") == "verify.started"]


def test_failing_command_feeds_failure_text_and_corrective_turn(tmp_path):
    prov = WriteThenDone()
    events = []
    turn = run_turns(
        prov, "write", _ctx(tmp_path), tool_protocol="prompt", max_turns=6,
        verify_command="exit 7", on_event=events.append,
    )
    started = [e for e in events if e.get("type") == "verify.started"]
    completed = [e for e in events if e.get("type") == "verify.completed"]
    assert started and completed and completed[0]["ok"] is False
    # corrective turn happened: call 2's messages contain the VERIFY FAILED text
    assert prov.calls >= 2
    last_user = [m for m in prov.seen[-1] if m["role"] == "user"]
    assert any("VERIFY FAILED" in str(m.get("content", "")) for m in last_user)
    assert turn.content == "done"


def test_passing_command_no_extra_correction(tmp_path):
    class OneShot(WriteThenDone):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls == 1:
                return Turn('TOOL_CALL: {"name": "write_file", "arguments": {"path": "ok.txt", "content": "y"}}')
            return Turn("fine")

    prov = OneShot()
    events = []
    run_turns(prov, "write", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=4, verify_command="true", on_event=events.append)
    completed = [e for e in events if e.get("type") == "verify.completed"]
    assert completed and completed[0]["ok"] is True
    assert prov.calls == 2  # write turn + final; no corrective turn


def test_max_verify_retries_no_infinite_loop(tmp_path):
    class LoopGuard(WriteThenDone):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls < 10:
                return Turn('TOOL_CALL: {"name": "write_file", "arguments": {"path": "out.txt", "content": "v%d"}}' % self.calls)
            return Turn("gave up")

    prov = LoopGuard()
    events = []
    run_turns(prov, "write", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=12, verify_command="exit 1", max_verify_retries=2,
              on_event=events.append)
    started = [e for e in events if e.get("type") == "verify.started"]
    assert len(started) == 2  # exactly two verify runs, then stops


def test_verify_output_charged_to_observation_budget(tmp_path):
    """A verify command producing huge output is PARTIAL-truncated by the budget."""
    prov = WriteThenDone()
    events = []
    turn = run_turns(
        prov, "write", _ctx(tmp_path), tool_protocol="prompt", max_turns=6,
        verify_command="python3 -c \"print('Z' * 9000)\"",
        observation_budget=500, on_event=events.append,
    )
    # failure path runs (exit 0? python succeeds -> ok True) — force failure:
    # rerun with failing + fat output
    events.clear()
    prov2 = WriteThenDone()
    run_turns(
        prov2, "write", _ctx(tmp_path), tool_protocol="prompt", max_turns=6,
        verify_command="python3 -c \"print('Z' * 9000); raise SystemExit(1)\"",
        observation_budget=500, on_event=events.append,
    )
    # the corrective user message carries the PARTIAL marker
    corrective = [m for m in prov2.seen[1] if m["role"] == "user"]
    import json as _j
    flat = _j.dumps(corrective)
    assert "VERIFY FAILED" in flat
    assert "PARTIAL" in flat or "[verify output trimmed]" in flat


def test_events_emitted_in_order(tmp_path):
    prov = WriteThenDone()
    events = []
    run_turns(prov, "write", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=6, verify_command="exit 1", on_event=events.append)
    types = [e.get("type") for e in events]
    # order: ... tool.completed (write) ... verify.started ... verify.completed
    ti = types.index("tool.completed")
    si = types.index("verify.started")
    ci = types.index("verify.completed")
    assert ti < si < ci


# -- 19F1: the reported exit code must be the command's real status ------


def test_verify_completed_reports_real_exit_code(tmp_path):
    """`exit 7` must surface as exit_code 7 — --json consumers read this."""
    events = []
    run_turns(
        WriteThenDone(), "write", _ctx(tmp_path), tool_protocol="prompt",
        max_turns=6, verify_command="exit 7", on_event=events.append,
    )
    completed = [e for e in events if e.get("type") == "verify.completed"]
    assert completed and completed[0]["exit_code"] == 7
    assert completed[0]["ok"] is False


def test_verify_completed_reports_zero_on_success(tmp_path):
    events = []
    run_turns(
        WriteThenDone(), "write", _ctx(tmp_path), tool_protocol="prompt",
        max_turns=6, verify_command="true", on_event=events.append,
    )
    completed = [e for e in events if e.get("type") == "verify.completed"]
    assert completed and completed[0]["exit_code"] == 0 and completed[0]["ok"] is True


def test_verify_timeout_reports_nonzero_code(tmp_path):
    ctx = _ctx(tmp_path)
    ctx.timeout = 1
    events = []
    run_turns(
        WriteThenDone(), "write", ctx, tool_protocol="prompt",
        max_turns=6, verify_command="sleep 30", on_event=events.append,
    )
    completed = [e for e in events if e.get("type") == "verify.completed"]
    assert completed and completed[0]["ok"] is False
    assert completed[0]["exit_code"] not in (0, 1)
