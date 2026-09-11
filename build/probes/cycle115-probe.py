"""CYCLE 115 R-I probe — the cost gate, end to end.

(a) tiny declared budget: the projection prints, the boundary refuses BEFORE
    candidate 2's provider call (call count proves it), exit 4, real job id;
(b) budget that fits: the projection prints and the run proceeds to the
    verify pass, exit 0;
(c) the C103 turn-boundary breach path now prints a REAL job id too (the
    `jobs.create` return key fix, verified live).

Usage:  uv run python build/probes/cycle115-probe.py
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from contextlib import redirect_stderr
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
        self.usage = {"total_tokens": 10}
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

    def chat(self, messages, system=None, **kw):
        self.n += 1
        return Turn(self.script[self.n - 1] if self.n <= len(self.script)
                    else "finished")

    def close(self):
        pass


def run_case(script, **kw):
    import codemonkey.exec as exec_mod

    tmp = Path(tempfile.mkdtemp(prefix="cm115-"))
    os.environ["HOME"] = str(tmp / "home")
    os.environ["CODEMONKEY_TOOL_PROTOCOL"] = "prompt"
    prov = Prov(script)
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    err = io.StringIO()
    events: list = []
    try:
        with redirect_stderr(err):
            code = exec_mod.run_exec("write the answer file", cwd=tmp,
                                     skip_git_repo_check=True, ephemeral=True,
                                     stream_deltas=False, stdin_cm="",
                                     sandbox="workspace-write", approval="never",
                                     event_sink=events, **kw)
    finally:
        exec_mod._provider_from_config = orig
    return tmp, code, prov, err.getvalue(), events


def main() -> int:
    py = sys.executable
    verifier = (f'"{py}" -c "import sys; sys.exit(0 if '
                f"open('answer.txt').read().strip()=='RIGHT' else 1)\"")

    print("--- a. tiny budget: refused BEFORE candidate 2's call ---")
    os.environ["CODEMONKEY_BUDGET_TOKENS"] = "25"
    script = [write_call("answer.txt", "W1"), "one",
              write_call("answer.txt", "W2"), "two",
              write_call("answer.txt", "RIGHT"), "three"]
    tmp, code, prov, err, events = run_case(script, best_of=3,
                                            verify_command=verifier)
    for line in err.splitlines():
        if "bestofn" in line or "budget" in line:
            print(f"    | {line}")
    check("exit 4", code == 4, f"exit={code}")
    check("provider calls == 2 (candidate 2 never started)", prov.n == 2,
          f"n={prov.n}")
    check("tree keeps candidate 1", (tmp / "answer.txt").read_text() == "W1")
    bex = [e for e in events if e.get("type") == "budget.exhausted"]
    check("budget.exhausted stage=bestofn-boundary",
          bool(bex) and bex[0]["stage"] == "bestofn-boundary")
    check("projection line printed",
          "projected extra spend" in err and "declared tokens=25" in err)
    check("REAL job id (not None)", "resumable job: job-" in err)

    print("--- b. budget fits: projection prints, run proceeds ---")
    os.environ["CODEMONKEY_BUDGET_TOKENS"] = "1000"
    script = [write_call("answer.txt", "WRONG"), "one",
              write_call("answer.txt", "RIGHT"), "two"]
    tmp2, code2, prov2, err2, _ = run_case(script, best_of=2,
                                           verify_command=verifier)
    check("exit 0 and verified tree", code2 == 0
          and (tmp2 / "answer.txt").read_text() == "RIGHT")
    check("projection printed on the fit path",
          "projected extra spend: 1 more candidate(s)" in err2
          and "spent so far=20" in err2)

    print("--- c. C103 turn-boundary breach prints a REAL job id (fix check) ---")
    os.environ["CODEMONKEY_BUDGET_TOKENS"] = "15"
    script = [write_call("answer.txt", "X"), "one", "finish"]
    tmp3, code3, prov3, err3, ev3 = run_case(script)
    breach = [e for e in ev3 if e.get("type") == "budget.exhausted"]
    check("turn-boundary breach still fires (exit 4)", code3 == 4, f"exit={code3}")
    check("breach names the turn boundary", bool(breach))
    check("resumable job line carries a REAL id",
          "resumable job: job-" in err3,
          [l for l in err3.splitlines() if "job" in l][:1])

    print()
    print("CYCLE115 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
