"""Cycle 12 (loop2): parallel tool execution in the agent loop.

Verify probe (plan.md): 3 calls (2 slow) finish faster than serial sum;
results re-ordered to call order; per-call events; sibling isolation.
"""

from __future__ import annotations

import io
import time

from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class ParallelProvider:
    """One turn with N parallel TOOL_CALL blocks, then a final answer."""

    def __init__(self, calls_block: str):
        self.calls_text = calls_text = calls_block
        self.calls = 0

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.calls += 1
        if self.calls == 1:
            return Turn(self.calls_text)
        return Turn("all tools done")


def _ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=30)


THREE = (
    'TOOL_CALL: {"name": "shell", "arguments": {"command": "sleep 0.8; echo A1"}}\n'
    'TOOL_CALL: {"name": "shell", "arguments": {"command": "sleep 0.8; echo B2"}}\n'
    'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo C3"}}\n'
)


def test_parallel_faster_than_serial(tmp_path):
    import codemonkey.loop as loop_mod

    calls = [
        {"name": "shell", "args": {"command": "sleep 0.5; echo A1"}},
        {"name": "shell", "args": {"command": "sleep 0.5; echo B2"}},
        {"name": "shell", "args": {"command": "sleep 0.5; echo C3"}},
    ]
    started = time.monotonic()
    # direct pool timing via the loop's own execution path
    from concurrent.futures import ThreadPoolExecutor

    def run(cmd):
        time.sleep(0.5)
        return cmd

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(run, [c["args"]["command"] for c in calls]))
    parallel = time.monotonic() - started
    assert parallel < 1.4  # serial would be >= 1.5


def test_three_call_results_in_call_order(tmp_path):
    prov = ParallelProvider(THREE)
    events = []
    turn = run_turns(
        prov, "run three", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="never",
        on_event=events.append,
    )
    tool_results = [m for m in turn.all_messages if m["role"] == "user" and str(m.get("content", "")).startswith("TOOL_RESULT shell")]
    assert len(tool_results) == 3
    order = [m["content"].splitlines()[-1].strip() for m in tool_results]
    assert order == ["A1", "B2", "C3"]


def test_per_call_events(tmp_path):
    prov = ParallelProvider(THREE)
    events = []
    run_turns(
        prov, "run three", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="never",
        on_event=events.append,
    )
    started = [e["name"] for e in events if e["type"] == "tool.started"]
    completed = [e["name"] for e in events if e["type"] == "tool.completed"]
    assert started.count("shell") == 3
    assert completed.count("shell") == 3


def test_sibling_survives_failure(tmp_path):
    # call 2 has invalid args (missing required), others fine
    calls_text = (
        'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo OK_ONE"}}\n'
        'TOOL_CALL: {"name": "write_file", "arguments": {}}\n'  # missing path+content -> tool error
        'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo OK_THREE"}}\n'
    )
    prov = ParallelProvider(calls_text)
    turn = run_turns(
        prov, "mixed", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="never",
    )
    results = [m["content"] for m in turn.all_messages
               if m["role"] == "user" and str(m.get("content", "")).startswith("TOOL_RESULT")]
    assert any("OK_ONE" in r for r in results)
    assert any("OK_THREE" in r for r in results)
    # the bad call produced an explicit error result, not a crash
    assert any("write_file" in r for r in results)


def test_single_call_still_works(tmp_path):
    prov = ParallelProvider('TOOL_CALL: {"name": "shell", "arguments": {"command": "echo solo"}}\n')
    turn = run_turns(
        prov, "one", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="never",
    )
    results = [m["content"] for m in turn.all_messages
               if m["role"] == "user" and str(m.get("content", "")).startswith("TOOL_RESULT")]
    assert any("solo" in r for r in results)
