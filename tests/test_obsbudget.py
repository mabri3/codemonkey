"""Cycle 17 (loop3): observation budget for tool outputs.

Verify probe (plan.md): >=4 tests — budget enforcement, marker format,
isolation across calls (ledger shared per run), under-budget untouched.
"""

from __future__ import annotations

from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class TwoFatOutputsProvider:
    """One turn: two fat shell outputs (python-generated); then final."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.calls += 1
        if self.calls == 1:
            return Turn(
                'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo {1..200}AAA"}}\n'
                'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo {1..200}BBB"}}\n'
            )
        return Turn("done")


def _ctx(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


def _results_of(all_messages):
    return [m["content"] for m in all_messages
            if m["role"] == "user" and str(m.get("content", "")).startswith("TOOL_RESULT shell")]


def test_over_budget_truncated_with_partial_marker(tmp_path):
    prov = TwoFatOutputsProvider()
    turn = run_turns(
        prov, "two fat outputs", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=4,
        observation_budget=60,  # tiny on purpose
    )
    results = _results_of(turn.all_messages)
    assert len(results) == 2
    # first call consumed the whole budget -> PARTIAL marker
    assert "[PARTIAL:" in results[0] and "full output saved to" in results[0]
    # second got nothing -> 0-allowance PARTIAL but still a marker, not raw dump
    assert "[PARTIAL:" in results[1]


def test_under_budget_untouched(tmp_path):
    class SmallProvider(TwoFatOutputsProvider):
        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls == 1:
                return Turn('TOOL_CALL: {"name": "shell", "arguments": {"command": "echo small"}}')
            return Turn("done")

    prov = SmallProvider()
    turn = run_turns(
        prov, "small", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=4,
        observation_budget=20000,
    )
    results = _results_of(turn.all_messages)
    assert results and "small" in results[0]
    assert "[PARTIAL:" not in results[0]


def test_marker_reports_elided_count(tmp_path):
    prov = TwoFatOutputsProvider()
    turn = run_turns(
        prov, "fat", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=4,
        observation_budget=50,
    )
    results = _results_of(turn.all_messages)
    first = results[0]
    import re
    m = re.search(r"\[PARTIAL: (\d+) chars total; full output saved to (\S+)", first)
    assert m, first[-200:]
    assert int(m.group(1)) > 0
    import os as _os
    assert _os.path.isfile(m.group(2))  # spill file exists


def test_ledger_shared_across_calls(tmp_path):
    """call A burns the budget; call B gets ~0 allowance (isolation preserved,
    both still delivered)."""
    prov = TwoFatOutputsProvider()
    turn = run_turns(
        prov, "fat pair", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=4,
        observation_budget=100,
    )
    results = _results_of(turn.all_messages)
    assert len(results) == 2
    # B must be shorter than a full second dump and contain the marker
    assert "PARTIAL" in results[1]
    assert len(results[1]) < 400
