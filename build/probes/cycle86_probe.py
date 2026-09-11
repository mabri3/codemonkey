"""CYCLE 86 R-I probe — the R-J revocation surface, through the CLI.

    show demo_ok          -> provenance incl. the originating run id
    revoke demo_ok        -> gone; the next skills=use prompt loses its line
    revoke nope           -> exit 2, refused not ignored
    disable               -> zero loads, evidence kept, the run still succeeds
    disable --enable      -> loads again
    journal               -> skill.revoked / skills.disabled / skills.enabled

Usage:  uv run python build/probes/cycle86_probe.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))


class Turn:
    def __init__(self, c):
        self.content = c
        self.usage = {}
        self.tool_calls = []


class Prov:
    protocol = "openai"

    def __init__(self):
        self.system = None

    def chat(self, messages, system=None, **kw):
        if self.system is None:
            self.system = system or ""
        return Turn("finished")


def cli(tmp: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "codemonkey.cli", "skills", *args],
        cwd=str(tmp), capture_output=True, text=True)


def prompt_for(tmp: Path) -> str:
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    prov = Prov()
    ctx = ToolContext(workdir=tmp, sandbox="workspace-write", timeout=30,
                      extra={"config": {"strategies": {"skills": "use"}}})
    run_turns(prov, "hi", ctx, tool_protocol="prompt", memory_enabled=False)
    return prov.system or ""


def main() -> int:
    from codemonkey import journal, skills

    with tempfile.TemporaryDirectory(prefix="cm86-") as td:
        tmp = Path(td)
        os.environ["HOME"] = str(tmp / ".home")
        skills.write_manifest(tmp, {
            "name": "demo_ok", "spec": "says hello",
            "params": {"type": "object", "properties": {}},
            "probe": "echo ok",
            "provenance": {"run_id": "r-orig", "session_id": "s1",
                           "taint_free": True},
            "status": "quarantined"})
        skills.set_status(tmp, "demo_ok", "admitted", reason="C86 probe")

        r = cli(tmp, "show", "demo_ok")
        print(f"$ codemonkey skills show demo_ok  [exit {r.returncode}]")
        print("\n".join("  " + ln for ln in r.stdout.splitlines()))

        pre = prompt_for(tmp)
        print(f"pre-revoke  prompt has 'demo_ok': {'demo_ok' in pre}")

        r = cli(tmp, "revoke", "demo_ok")
        print(f"$ codemonkey skills revoke demo_ok  [exit {r.returncode}]")
        print(f"  {r.stdout.strip()}")
        post = prompt_for(tmp)
        print(f"post-revoke prompt has 'demo_ok': {'demo_ok' in post}")
        r = cli(tmp, "list")
        print(f"$ codemonkey skills list  [exit {r.returncode}]  -> {r.stdout.strip()}")

        r = cli(tmp, "revoke", "nope")
        print(f"$ codemonkey skills revoke nope  [exit {r.returncode}]  "
              f"{(r.stdout + r.stderr).strip()}")

        # disable: evidence kept, zero loads, run still succeeds
        skills.write_manifest(tmp, {
            "name": "demo_two", "spec": "second", 
            "params": {"type": "object", "properties": {}},
            "probe": "echo ok",
            "provenance": {"run_id": "r2", "session_id": "s2",
                           "taint_free": True},
            "status": "quarantined"})
        skills.set_status(tmp, "demo_two", "admitted", reason="probe")
        r = cli(tmp, "disable")
        print(f"$ codemonkey skills disable  [exit {r.returncode}]  {r.stdout.strip()}")
        print(f"  load_admitted while disabled: {skills.load_admitted(tmp)}")
        print(f"  list still shows evidence: {[x['name'] for x in skills.list_skills(tmp)]}")
        print(f"  disabled prompt has 'demo_two': {'demo_two' in prompt_for(tmp)}")
        r = cli(tmp, "disable", "--enable")
        print(f"$ codemonkey skills disable --enable  [exit {r.returncode}]  "
              f"{r.stdout.strip()}")
        print(f"  load_admitted after enable: "
              f"{[x['name'] for x in skills.load_admitted(tmp)]}")

        print("--- journal ---")
        for rec in journal.read_thread(skills.skill_thread(tmp)):
            if str(rec.get("type", "")).startswith("skill"):
                print(f"  {rec['type']} key={rec.get('key')} status={rec.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
