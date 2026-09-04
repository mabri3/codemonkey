"""CYCLE 74 F7 fixture probe (LIVE-probe fallback; in-process R-I grammar).

The plan's F7 LIVE probe (`exec --json "Use the graph_query tool ..."`)
needs the model endpoint. The endpoint probe is BLOCKED this run (terminal
consent gate on network probes — recorded in BUILD_LOG). Fallback per the
R-I grammar: a scripted fake provider drives the REAL run_exec and asserts
the graph_query tool trace in the --json event stream.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "src"))

os.environ["CODEMONKEY_TOOL_PROTOCOL"] = "prompt"  # dodge endpoint native-tools quirk


class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class GraphToolProv:
    """Turn 1: call graph_query('run_turns') via the prompt protocol. Turn 2: stop."""

    protocol = "openai"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            return Turn('TOOL_CALL: {"name": "graph_query", "arguments": '
                        '{"symbol": "run_turns"}}\n')
        return Turn("done — looked up run_turns in the graph")

    def close(self):
        pass


def main() -> int:
    import codemonkey.exec as exec_mod

    prov = GraphToolProv()
    orig = exec_mod._provider_from_config
    with tempfile.TemporaryDirectory() as td:
        os.environ["HOME"] = str(Path(td) / "home")
        (Path(td) / "home").mkdir()
        exec_mod._provider_from_config = (
            lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
        try:
            events: list = []
            code = exec_mod.run_exec(
                "Use the graph_query tool to look up 'run_turns' in this "
                "repo's code graph, then report one edge you saw.",
                cwd=REPO, skip_git_repo_check=True, ephemeral=True,
                stream_deltas=False, stdin_cm="", sandbox="read-only",
                approval="never", event_sink=events, max_turns=4)
        finally:
            exec_mod._provider_from_config = orig

    types = [e.get("type") for e in events]
    tool_calls = [e for e in events if e.get("type") == "tool.started"]
    names = [e.get("name") for e in tool_calls]
    blob = json.dumps(events)
    print(f"exit_code={code}")
    print(f"tool names: {names}")
    print(f"provider turns used: {prov.n}")
    assert code == 0, f"run failed: {code}"
    assert "graph_query" in names, "graph_query never entered the tool trace"
    assert "matches for 'run_turns'" in blob, "tool result text missing from events"
    assert 'cycle' in blob or 'edge' in blob, "no edge content in trace"
    print("PROBE OK: real run_exec executed graph_query; trace shows the "
          "match block + edges from this repo's graphify-out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
