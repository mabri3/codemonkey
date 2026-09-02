"""Cycle 7F1: memory strategy wiring — prompt injection + update_memory tool.

Verify probe (plan.md): >=4 tests — fact verbatim in the system arg;
memory=none hides fact AND update_memory from the prompt block; update_memory
appends idempotently; unknown memory name exits 2 with valid names.
"""

from __future__ import annotations

import pytest
from codemonkey.instructions import build_project_context_block
from codemonkey.loop import run_turns
from codemonkey.protocol import prompt_block
from codemonkey.sandbox import ToolContext
from codemonkey.strategies.memory import FileMemory, NoMemory, get_memory
from codemonkey.tools import SPECS, dispatch


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class SpyProvider:
    protocol = "openai"

    def __init__(self):
        self.seen = []

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.seen.append({"messages": list(messages), "system": system})
        return Turn("ok")


def _ctx(tmp, extra=None):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10,
                       extra=extra or {})


PROBE = "codemonkey_memory_probe_token"


def test_fact_appears_verbatim_in_system(tmp_path, monkeypatch):
    mem = FileMemory(path=tmp_path / "memory.md")
    mem.add_fact(f"probe: {PROBE}")
    from codemonkey.instructions import load_instructions

    block = build_project_context_block(tmp_path, instructions=load_instructions(tmp_path),
                                        memory_text=mem.load())
    prov = SpyProvider()
    run_turns(prov, "hi", _ctx(tmp_path), tool_protocol="prompt", max_turns=2,
              system_extra=block, memory_enabled=True)
    assert PROBE in prov.seen[0]["system"]


def test_memory_none_hides_fact_and_tool(tmp_path):
    mem = FileMemory(path=tmp_path / "memory.md")
    mem.add_fact(f"probe: {PROBE}")
    # none strategy: no text, and update_memory not advertised
    none_mem = NoMemory()
    block = build_project_context_block(tmp_path, instructions="", memory_text=none_mem.load())
    assert PROBE not in block
    system = prompt_block(SPECS, memory_enabled=False)
    assert "update_memory" not in system
    # and enabled=True keeps it advertised
    assert "update_memory" in prompt_block(SPECS, memory_enabled=True)


def test_update_memory_appends_and_idempotent(tmp_path):
    mem = FileMemory(path=tmp_path / "memory.md")
    r1 = dispatch("update_memory", {"fact": "likes turtles"}, _ctx(tmp_path, {"memory": mem}))
    assert r1.ok and mem.load() == "likes turtles"
    r2 = dispatch("update_memory", {"fact": "likes turtles"}, _ctx(tmp_path, {"memory": mem}))
    assert r2.ok and mem.load() == "likes turtles"  # idempotent, no dup
    # disabled memory -> honest error
    r3 = dispatch("update_memory", {"fact": "x"}, _ctx(tmp_path, {"memory": None}))
    assert not r3.ok and "disabled" in r3.output


def test_update_memory_advertised_in_specs():
    assert "update_memory" in SPECS


def test_unknown_memory_name_exit2():
    from codemonkey.config import ConfigError, load_config

    with pytest.raises((ConfigError, ValueError)) as exc:
        cfg = load_config(overrides={"strategies.memory": "banana"},
                          ignore_user_config=True)
    assert "file" in str(exc.value) and "none" in str(exc.value)


def test_get_memory_none_returns_nomemory(tmp_path):
    m = get_memory("none")
    assert isinstance(m, NoMemory)
    assert m.load() == ""
    m.add_fact("ignored")
    assert m.load() == ""
