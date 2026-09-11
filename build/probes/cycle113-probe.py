"""CYCLE 113 R-I probe — the refine pass through the real exec path.

Part A (released CLI, no provider needed): `--refine-seeded` surfaces in
--help; the flag without --best-of N>1 refuses with exit 2 and the reason.
Part B (in-process, scripted provider through the REAL run_exec): two
candidates fail, the refine is seeded with their bounded evidence, the
refined tree stands, `bestofn.refine {candidates:2, refined:1, verified:true}`
is in the trace.

Usage:  uv run python build/probes/cycle113-probe.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global FAIL
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAIL = 1


class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


def write_call(path, content):
    import json as _json
    return ('TOOL_CALL: {"name": "write_file", "arguments": '
            + _json.dumps({"path": path, "content": content}) + '}\n')


class Prov:
    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.n = 0
        self.seen = []

    def chat(self, messages, system=None, **kw):
        self.n += 1
        self.seen.append("\n".join(str(m.get("content", "")) for m in messages
                                   if m.get("role") == "user"))
        return Turn(self.script[self.n - 1] if self.n <= len(self.script)
                    else "finished")

    def close(self):
        pass


def main() -> int:
    print("--- A. released CLI surface (flags BEFORE the positional — the")
    print("       exec group's variadic prompt swallows trailing flags; every")
    print("       exec flag has this order, not just this one) ---")
    env = dict(os.environ)
    cm = ["uv", "run", "--quiet", "--project", str(ROOT), "codemonkey"]
    h = subprocess.run(cm + ["exec", "--help"], capture_output=True, text=True,
                       env=env)
    check("--refine-seeded in exec --help", "--refine-seeded" in h.stdout)
    r = subprocess.run(cm + ["exec", "--refine-seeded", "--skip-git-repo-check", "x"],
                       capture_output=True, text=True, cwd=str(ROOT), env=env)
    check("flag without --best-of refuses exit 2", r.returncode == 2,
          f"exit={r.returncode}")
    check("refusal names the reason",
          "refine-seeded" in (r.stderr + r.stdout))

    print("--- B. scripted refine run through REAL run_exec ---")
    import codemonkey.exec as exec_mod
    from codemonkey.exec import run_exec

    tmp = Path(tempfile.mkdtemp(prefix="cm113-"))
    os.environ["HOME"] = str(tmp / "home")
    os.environ["CODEMONKEY_TOOL_PROTOCOL"] = "prompt"
    py = sys.executable
    verifier = (f'"{py}" -c "import sys; sys.exit(0 if '
                f"open('answer.txt').read().strip()=='RIGHT' else 1)\"")

    prov = Prov([
        write_call("answer.txt", "WRONG1"), "attempt one done",
        write_call("answer.txt", "WRONG2"), "attempt two done",
        write_call("answer.txt", "RIGHT"), "refined done",
    ])
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    events: list = []
    try:
        code = run_exec("write the answer file", cwd=tmp,
                        skip_git_repo_check=True, ephemeral=True,
                        stream_deltas=False, stdin_cm="",
                        sandbox="workspace-write", approval="never",
                        best_of=2, verify_command=verifier,
                        refine_seeded=True, event_sink=events)
    finally:
        exec_mod._provider_from_config = orig

    ref = [e for e in events if e.get("type") == "bestofn.refine"]
    done = [e for e in events if e.get("type") == "bestofn.completed"]
    print(f"  exit={code} answer={ (tmp / 'answer.txt').read_text()!r}")
    print(f"  refine event: {ref[0] if ref else None}")
    check("exit 0 and the refined tree stands",
          code == 0 and (tmp / "answer.txt").read_text() == "RIGHT")
    check("bestofn.refine: candidates=2 refined=1 verified=True",
          bool(ref) and ref[0]["candidates"] == 2 and ref[0]["refined"] == 1
          and ref[0]["verified"] is True)
    check("completed carries refined=True",
          bool(done) and done[0]["ok"] is True and done[0].get("refined") is True)
    seed_received = any("[candidate 1]" in s and "[candidate 2]" in s
                        and "failed its machine check" in s for s in prov.seen)
    check("the refine prompt carried both candidates' bounded evidence",
          seed_received)

    print()
    print("CYCLE113 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
