"""CYCLE 108 R-I probe — the reflector, end to end through the RELEASED CLI.

A scripted provider drives the REAL run_turns loop into two shell failures
(a command that does not exist, twice) and one malformed write_file call.
Then: `codemonkey playbook reflect <thread>` prints the deltas (JSON), a
second reflect is byte-identical, and `playbook merge` lands them
quarantined — with evidence indexes and the coarse taint posture visible.

Usage:  uv run python build/probes/cycle108-probe.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

THREAD = "probe-r108"
FAIL = 0


class Turn:
    def __init__(self, c):
        self.content = c
        self.usage = {}
        self.tool_calls = []


class Prov:
    protocol = "openai"

    def __init__(self, script):
        self.script = script
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        return Turn(self.script[self.n - 1] if self.n - 1 < len(self.script)
                    else "done")


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAIL
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL = 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="cm108-"))
    ws = tmp / "ws"
    ws.mkdir()
    os.environ["HOME"] = str(tmp / ".home")

    from codemonkey import journal, playbook
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    shell_bad = {"name": "shell", "arguments": {"command": "xyzzy-not-a-command"}}
    wf_bad = {"name": "write_file", "arguments": {"path": "no-content.txt"}}
    script = ["TOOL_CALL: " + json.dumps(shell_bad),
              "TOOL_CALL: " + json.dumps(shell_bad),
              "TOOL_CALL: " + json.dumps(wf_bad),
              "stopped"]

    print("--- 1. scripted failing run through the REAL loop ---")
    ctx = ToolContext(workdir=ws, sandbox="workspace-write", timeout=30,
                      extra={"config": {}, "session_id": THREAD, "run_id": "r108"})
    events: list = []
    run_turns(Prov(script), "go", ctx, tool_protocol="prompt", max_turns=8,
              memory_enabled=False, on_event=events.append,
              journal_thread=THREAD, journal_run="j108")
    records = journal.read_thread(THREAD)
    outs = [(i, r.get("tool"), r.get("status"), r.get("error_class"))
            for i, r in enumerate(records) if r.get("type") == "outcome"]
    print(f"  outcome records (index, tool, status, class): {outs}")
    check("two shell error records exist",
          sum(1 for _, t, s, _ in outs if t == "shell" and s == "error") == 2)
    check("one write_file error record exists",
          any(t == "write_file" and s == "error" for _, t, s, _ in outs))

    print("--- 2. reflect (in-process): grouping + evidence + taint ---")
    deltas = playbook.reflect(records, thread=THREAD)
    print(json.dumps(deltas, indent=2))
    shell_d = [d for d in deltas if d["text"].startswith("shell")]
    wf_d = [d for d in deltas if d["text"].startswith("write_file")]
    check("one shell delta, one write_file delta",
          len(shell_d) == 1 and len(wf_d) == 1)
    if shell_d and wf_d:
        check("shell evidence cites BOTH failing records",
              len(shell_d[0]["evidence"]) == 2, str(shell_d[0]["evidence"]))
        check("write_file evidence cites its record",
              len(wf_d[0]["evidence"]) == 1)
        check("shell group is taint-marked (stdout source)",
              shell_d[0]["provenance"]["taint_free"] is False)
        check("write_file group is clean",
              wf_d[0]["provenance"]["taint_free"] is True)
    check("store does not exist after reflection (no side effect)",
          not playbook.store_path(ws).exists())

    print("--- 3. CLI reflect: JSON out, byte-identical on re-run ---")
    env = dict(os.environ)
    cm = ["uv", "run", "--quiet", "--project", str(ROOT), "codemonkey"]
    r1 = subprocess.run(cm + ["playbook", "reflect", THREAD], cwd=ws, env=env,
                        capture_output=True, text=True)
    r2 = subprocess.run(cm + ["playbook", "reflect", THREAD], cwd=ws, env=env,
                        capture_output=True, text=True)
    check("reflect exits 0", r1.returncode == 0, f"exit={r1.returncode}")
    check("reflect output is byte-identical on re-run", r1.stdout == r2.stdout)
    cli_deltas = json.loads(r1.stdout)
    check("CLI deltas equal in-process deltas", cli_deltas == deltas)
    deltas_file = ws / "deltas.json"
    deltas_file.write_text(r1.stdout)

    print("--- 4. CLI merge: quarantined, evidenced, not loaded ---")
    r3 = subprocess.run(cm + ["playbook", "merge", str(deltas_file)], cwd=ws,
                        env=env, capture_output=True, text=True)
    print(f"  {r3.stdout.strip()}")
    check("merge exits 0 and adds both deltas",
          r3.returncode == 0 and "added=2" in r3.stdout)
    r4 = subprocess.run(cm + ["playbook", "list"], cwd=ws, env=env,
                        capture_output=True, text=True)
    print(f"  {r4.stdout.strip()}")
    check("both entries quarantined in the CLI listing",
          r4.stdout.count("quarantined") == 2)
    rows = playbook.list_entries(ws)
    check("load_admitted empty (quarantine holds)", playbook.load_admitted(ws) == [])
    check("evidence persisted on disk",
          sorted(e["evidence"] for e in rows if e["text"].startswith("shell"))
          == [sorted(shell_d[0]["evidence"])] if shell_d else False)

    print("--- 5. reflection vs store: reflecting again changes NOTHING ---")
    r5 = subprocess.run(cm + ["playbook", "reflect", THREAD], cwd=ws, env=env,
                        capture_output=True, text=True)
    check("re-reflect after merge is still byte-identical (store untouched by reflect)",
          r5.stdout == r1.stdout)

    print()
    print("CYCLE108 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
