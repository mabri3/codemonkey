"""CYCLE 114 R-I probe — the tournament selector through the CLI surface.

`codemonkey exec --best-of 2 --tournament-compare <cmd> <prompt>` (flags
BEFORE the positional) with a scripted provider: the command picks candidate
2, the WINNER's tree stands, exit 0, stdout carries the winner's message. A
malformed command refuses the selection (exit 1) and the LAST tree stays.

Usage:  uv run python build/probes/cycle114-probe.py
"""

from __future__ import annotations

import json
import os
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
    return ('TOOL_CALL: {"name": "write_file", "arguments": '
            + json.dumps({"path": path, "content": content}) + '}\n')


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


def run_cli(ws: Path, args: list, script: list):
    import codemonkey.exec as exec_mod
    from codemonkey.cli import app
    from typer.testing import CliRunner

    prov = Prov(script)
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    cwd0 = os.getcwd()
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(ws / "home")
    os.environ["CODEMONKEY_TOOL_PROTOCOL"] = "prompt"
    os.chdir(ws)
    try:
        r = CliRunner().invoke(app, args)
    finally:
        os.chdir(cwd0)
        exec_mod._provider_from_config = orig
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    return r, prov


def main() -> int:
    print("--- 1. help carries the option ---")
    import subprocess

    h = subprocess.run(["uv", "run", "--quiet", "--project", str(ROOT),
                        "codemonkey", "exec", "--help"],
                       capture_output=True, text=True)
    check("--tournament-compare in exec --help",
          "--tournament-compare" in h.stdout)

    print("--- 2. the command's pick wins (candidate 2), tree restored ---")
    ws = Path(tempfile.mkdtemp(prefix="cm114-"))
    cmp = ws / "cmp.sh"
    cmp.write_text('if grep -q two "$1"; then echo a; '
                   'elif grep -q two "$2"; then echo b; else echo equal; fi\n')
    script = [
        write_call("answer.txt", "ONE"), "attempt one done",
        write_call("answer.txt", "TWO"), "attempt two done",
    ]
    r, prov = run_cli(ws, ["exec", "--best-of", "2",
                           "--tournament-compare", f"bash {cmp}",
                           "--skip-git-repo-check", "write the answer file"],
                      script)
    print(f"  exit={r.exit_code}  stdout={ (r.output or '').strip()!r}")
    print(f"  answer.txt={(ws / 'answer.txt').read_text()!r}")
    check("exit 0", r.exit_code == 0, f"exit={r.exit_code}")
    check("winner's tree stands (attempt 2)", (ws / "answer.txt").read_text() == "TWO")
    check("stdout carries the WINNER's message",
          "attempt two done" in (r.output or ""))

    print("--- 3. malformed command refuses; last tree stays; exit 1 ---")
    ws2 = Path(tempfile.mkdtemp(prefix="cm114b-"))
    bad = ws2 / "bad.sh"
    bad.write_text("echo maybe\n")
    script2 = [
        write_call("answer.txt", "ONE"), "attempt one done",
        write_call("answer.txt", "TWO"), "attempt two done",
    ]
    r2, _ = run_cli(ws2, ["exec", "--best-of", "2",
                          "--tournament-compare", f"bash {bad}",
                          "--skip-git-repo-check", "write the answer file"],
                    script2)
    print(f"  exit={r2.exit_code}  answer.txt={(ws2 / 'answer.txt').read_text()!r}")
    check("exit 1", r2.exit_code == 1, f"exit={r2.exit_code}")
    check("last tree KEPT", (ws2 / "answer.txt").read_text() == "TWO")

    print()
    print("CYCLE114 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
