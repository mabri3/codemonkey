"""Cycle 74 entry-point probe: a REAL `run_exec` run whose tool trace contains
`graph_query` (R-I: the feature is driven through exec, not pytest alone).

Fake provider scripted to emit a prompt-protocol graph_query call, then a final
answer; events captured through the real exec path (json_mode), graded here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codemonkey.providers.base import ChatTurn
import codemonkey.exec as exec_mod


class ScriptedGraphProvider:
    """Turn 1: call graph_query. Turn 2: final answer naming the edge."""

    protocol = "openai"

    def __init__(self):
        self.calls = 0
        self.systems = []

    def chat(self, messages, system=None, **kw):
        self.calls += 1
        self.systems.append(system or "")
        if self.calls == 1:
            return ChatTurn(
                content='TOOL_CALL: {"name": "graph_query", "arguments": {"symbol": "run_turns"}}',
                usage={"prompt_tokens": 10, "completion_tokens": 5},
            )
        return ChatTurn(
            content="run_turns (loop.py) references ProviderBase and ToolContext.",
            usage={"prompt_tokens": 20, "completion_tokens": 8},
        )

    def list_models(self):
        return ["scripted"]

    def close(self):
        pass


def main() -> int:
    workdir = Path(__file__).resolve().parents[1]  # repo root (has graphify-out/)
    events: list = []
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, ScriptedGraphProvider()

    exec_mod._provider_from_config = patched
    try:
        code = exec_mod.run_exec(
            "Use the graph_query tool to look up run_turns, then name one "
            "module-level thing it references.",
            json_mode=True,
            cwd=workdir,
            ephemeral=True,
            event_sink=events,
            stream_deltas=False,
            stdin_cm="",
        )
    finally:
        exec_mod._provider_from_config = orig

    tools_called = [ev.get("name") for ev in events if ev.get("type") == "tool.started"]
    print(json.dumps({"exit_code": code, "tool_trace": tools_called}, indent=2))
    assert code == 0, code
    assert "graph_query" in tools_called, tools_called
    completed = [ev for ev in events
                 if ev.get("type") == "item.completed"
                 and ev.get("item", {}).get("type") == "agent_message"]
    assert completed and "ProviderBase" in completed[-1]["item"]["text"]
    print("CYCLE74 PROBE: PASS — graph_query appears in a real run's tool trace")
    with open("build/probes/cycle74-tooltrace.json", "w") as f:
        json.dump({"tool_trace": tools_called, "exit_code": code,
                   "events": [e.get("type") for e in events]}, f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
