"""Cycle 16 (loop3): self-heal edit retries.

Verify probe (plan.md): >=4 tests — retry-on-failure carries the error text,
success-after-retry transcript shape, no retry when the edit succeeds, retry
limit respected (no infinite loop).
"""

from __future__ import annotations

from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class EditFlakyProvider:
    """Turn 1: bad edit (SEARCH text absent). Turn 2: reads, corrected edit.

    Turn 3: final answer.
    """

    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.calls = 0
        self.saw_feedback = None

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.calls += 1
        if self.calls == 1:
            return Turn('TOOL_CALL: {"name": "edit_file", "arguments": {"path": "f.txt", "old_string": "WRONG TEXT", "new_string": "new"}}')
        if self.calls == 2:
            # self-heal coach message must be the last user message
            last = messages[-1]["content"]
            self.saw_feedback = "Your edit_file call failed" in last and "error:" in last
            return Turn('TOOL_CALL: {"name": "edit_file", "arguments": {"path": "f.txt", "old_string": "real", "new_string": "REAL"}}')
        return Turn("fixed it")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


def test_retry_after_edit_failure(tmp_path):
    (tmp_path / "f.txt").write_text("real content\n")
    prov = EditFlakyProvider(tmp_path)
    events = []
    turn = run_turns(
        prov, "edit the file", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=6,
        on_event=events.append,
    )
    assert prov.saw_feedback, "coach message with error text not delivered"
    assert (tmp_path / "f.txt").read_text() == "REAL content\n"
    notices = [e for e in events if e.get("type") == "notice" and "self-heal" in e.get("message", "")]
    assert notices
    assert turn.content == "fixed it"


def test_no_retry_when_edit_ok(tmp_path):
    class OkProvider(EditFlakyProvider):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls == 1:
                return Turn('TOOL_CALL: {"name": "edit_file", "arguments": {"path": "f.txt", "old_string": "real", "new_string": "edited"}}')
            return Turn("done")

    (tmp_path / "f.txt").write_text("real content\n")
    prov = OkProvider(tmp_path)
    events = []
    run_turns(
        prov, "edit", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5,
        on_event=events.append,
    )
    assert not [e for e in events if e.get("type") == "notice" and "self-heal" in e.get("message", "")]
    assert prov.calls == 2  # no extra retry turn


def test_retry_limit_respected(tmp_path):
    class AlwaysFailsProvider(EditFlakyProvider):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls >= 3:
                return Turn("giving up")
            return Turn('TOOL_CALL: {"name": "edit_file", "arguments": {"path": "f.txt", "old_string": "WRONG", "new_string": "x"}}')

    (tmp_path / "f.txt").write_text("real\n")
    prov = AlwaysFailsProvider(tmp_path)
    events = []
    run_turns(
        prov, "edit", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=8, max_edit_retries=1,
        on_event=events.append,
    )
    notices = [e for e in events if e.get("type") == "notice" and "self-heal" in e.get("message", "")]
    assert len(notices) == 1  # only ONE retry granted
    assert prov.calls == 3    # initial + retry + final answer


def test_non_edit_failures_do_not_retry(tmp_path):
    class ShellFailProvider(EditFlakyProvider):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls == 1:
                return Turn('TOOL_CALL: {"name": "shell", "arguments": {"command": "exit 3"}}')
            return Turn("shell failed, that is fine")

    prov = ShellFailProvider(tmp_path)
    events = []
    run_turns(
        prov, "run", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5,
        on_event=events.append,
    )
    assert not [e for e in events if e.get("type") == "notice" and "self-heal" in e.get("message", "")]
