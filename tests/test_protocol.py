"""Cycle 4: tool protocol (prompt + native) and the agent loop."""

from __future__ import annotations

import json

import pytest

from codemonkey import protocol
from codemonkey.loop import FallbackRecorded, looks_like_tools_rejection, run_turns
from codemonkey.native import openai_tool_specs
from codemonkey.providers.base import ChatTurn, ProviderError
from codemonkey.providers.openai import _native_openai_tool_calls
from codemonkey.sandbox import ToolContext


# --------------------------------------------------------------------------
# parse_tool_calls
# --------------------------------------------------------------------------

def test_parse_unfenced_single():
    text = 'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo hi"}}'
    calls, prose = protocol.parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0]["name"] == "shell"
    assert calls[0]["args"] == {"command": "echo hi"}
    assert "error" not in calls[0]
    assert prose == ""


def test_parse_fenced_single():
    text = (
        "Let me check.\n"
        "```json\n"
        'TOOL_CALL: {"name": "read_file", "arguments": {"path": "a.py"}}\n'
        "```\n"
    )
    calls, prose = protocol.parse_tool_calls(text)
    assert calls and calls[0]["name"] == "read_file"
    assert calls[0]["args"] == {"path": "a.py"}
    assert prose == "Let me check."


def test_parse_multi_call():
    text = (
        'TOOL_CALL: {"name": "list_dir", "arguments": {"path": "."}}\n'
        'TOOL_CALL: {"name": "glob", "arguments": {"pattern": "*.py"}}\n'
        "done calling\n"
    )
    calls, prose = protocol.parse_tool_calls(text)
    assert [c["name"] for c in calls] == ["list_dir", "glob"]
    assert prose == "done calling"


def test_parse_garbage_tolerance():
    calls, prose = protocol.parse_tool_calls(
        "some prose\nTOOL_CALL: {not valid json,,}\nmore prose"
    )
    assert len(calls) == 1
    assert "error" in calls[0]
    assert "some prose" in prose and "more prose" in prose


def test_parse_marker_then_fenced_body():
    text = (
        "TOOL_CALL:\n"
        "```json\n"
        '{"name": "shell", "arguments": {"command": "ls"}}\n'
        "```\n"
    )
    calls, _ = protocol.parse_tool_calls(text)
    assert calls and calls[0]["name"] == "shell"
    assert calls[0]["args"] == {"command": "ls"}


def test_parse_no_calls_is_prose():
    calls, prose = protocol.parse_tool_calls("Just a final answer.\nSecond line.")
    assert calls == []
    assert "final answer" in prose


def test_prompt_block_advertises_specs():
    block = protocol.prompt_block({"shell": "shell(command) -> run it"})
    assert "TOOL_CALL:" in block
    assert "shell(command)" in block


# --------------------------------------------------------------------------
# native extraction
# --------------------------------------------------------------------------

def test_native_openai_tool_call_extraction():
    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "shell",
                "arguments": '{"command": "echo hi"}',
            },
        }
    ]
    out = _native_openai_tool_calls(tool_calls)
    assert out == [{"name": "shell", "args": {"command": "echo hi"}}]


def test_native_openai_tool_call_bad_json_preserved():
    tool_calls = [{"function": {"name": "shell", "arguments": "{oops"}}]
    out = _native_openai_tool_calls(tool_calls)
    assert out[0]["name"] == "shell"
    assert out[0]["args"] == {"_raw": "{oops"}


def test_native_openai_spec_shape():
    specs = openai_tool_specs({"shell": "shell(command) -> run it"})
    assert specs[0]["type"] == "function"
    assert specs[0]["function"]["name"] == "shell"
    assert "parameters" in specs[0]["function"]


# --------------------------------------------------------------------------
# loop over a scripted fake provider
# --------------------------------------------------------------------------

class FakeProvider:
    """Replays scripted responses; raises ProviderError for scripted errors."""

    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.calls: list[dict] = []

    def chat(self, messages, *, system=None, stream=False, max_tokens=None,
             temperature=None, tools=None, on_token=None, cache_prompt=True):
        self.calls.append({"tools": tools, "messages": list(messages)})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write")


def _call(name, args):
    return f'TOOL_CALL: {json.dumps({"name": name, "arguments": args})}'


def test_loop_two_calls_then_answer(ctx):
    p = FakeProvider([
        ChatTurn(content=f'{_call("list_dir", {"path": "."})}\n'
                         f'{_call("write_file", {"path": "x.txt", "content": "hi"})}'),
        ChatTurn(content="all done"),
    ])
    turn = run_turns(p, "do it", ctx, tool_protocol="prompt")
    assert turn.content == "all done"
    second = p.calls[1]["messages"]
    results = [m for m in second if str(m.get("content", "")).startswith("TOOL_RESULT")]
    assert len(results) == 2
    assert (ctx.workdir / "x.txt").read_text() == "hi"


def test_loop_max_turns_bails(ctx):
    p = FakeProvider([ChatTurn(content=_call("list_dir", {"path": "."}))
                      for _ in range(30)])
    events: list[dict] = []
    run_turns(p, "loop forever", ctx, tool_protocol="prompt",
              max_turns=3, on_event=events.append)
    assert len(p.calls) == 3
    assert any(
        e["type"] == "error" and "max_turns" in e["message"] for e in events
    )


def test_loop_error_result_feedback(ctx):
    p = FakeProvider([
        ChatTurn(content=_call("nope_tool", {})),
        ChatTurn(content="sorry, wrong tool"),
    ])
    turn = run_turns(p, "x", ctx, tool_protocol="prompt")
    assert turn.content == "sorry, wrong tool"
    fed = p.calls[1]["messages"][-1]["content"]
    assert "unknown tool 'nope_tool'" in fed


def test_loop_native_path_uses_turn_tool_calls(ctx):
    t1 = ChatTurn(content="", tool_calls=[{"name": "write_file",
                                           "args": {"path": "n.txt", "content": "y"}}])
    p = FakeProvider([t1, ChatTurn(content="written")])
    turn = run_turns(p, "x", ctx, tool_protocol="native")
    assert turn.content == "written"
    assert (ctx.workdir / "n.txt").read_text() == "y"


def test_auto_falls_back_on_tools_rejection(ctx):
    """The A9 mechanic: server 500s on the `tools` param -> prompt protocol,
    remembered for the provider, assistant reply returned."""
    p = FakeProvider([
        ProviderError('HTTP 500: property "tools" is unsupported', status=500),
        ChatTurn(content="fallback answer"),
    ])
    fb = FallbackRecorded()
    events: list[dict] = []
    turn = run_turns(p, "hi", ctx, tool_protocol="auto", fallback=fb,
                     on_event=events.append)
    assert turn.content == "fallback answer"
    assert p.calls[0]["tools"] is not None
    assert p.calls[1]["tools"] is None
    assert fb.must_prompt(p)
    assert any(e.get("type") == "notice" for e in events)


def test_looks_like_tools_rejection():
    assert looks_like_tools_rejection(
        ProviderError('HTTP 500 from x: unknown field "tools"', status=500)
    )
    assert not looks_like_tools_rejection(ProviderError("boom", status=500))
    assert not looks_like_tools_rejection(ProviderError('tools-ish', status=None))
