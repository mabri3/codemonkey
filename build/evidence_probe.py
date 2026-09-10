"""CYCLE 105 entry probe (R-I): the evidence pack through the CLI.

pytest alone never qualifies. This drives the RELEASED BINARY against a
scripted endpoint, takes the thread it produced, cuts a pack with
`codemonkey evidence pack`, verifies it with `codemonkey evidence verify`,
then TAMPERS with the pack and shows verify go red — the CLI path, not the
module in isolation.

Usage:  uv run python build/evidence_probe.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = Path(sys.executable).parent / "codemonkey"

_spec = importlib.util.spec_from_file_location(
    "sweep_driver", ROOT / "build" / "sweep_endpoint_gated.py")
assert _spec and _spec.loader
driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(driver)

SCRIPT = {
    "model": "stub-model",
    "turns": ["done"],
    "rules": [{"contains": "codemonkey_tool_test",
               "reply": 'TOOL_CALL: {"name": "shell", "arguments": '
                        '{"command": "echo codemonkey_tool_test"}}',
               "once": True}],
}


def run(args: list, env: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([str(BIN), *args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=300,
                          stdin=subprocess.DEVNULL)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cm-evidence-") as td:
        tmp = Path(td)
        home = tmp / "home"
        home.mkdir()
        with driver.Stub(SCRIPT) as stub:
            env = stub.env()
            env["HOME"] = str(home)          # isolate the journal
            env["CODEMONKEY_API_KEY"] = "stub-key"

            # 1. a real run that journals. The prompt must contain the stub
            # rule's trigger or the scripted tool call never fires and the run
            # writes no journal records (found by this probe's first run).
            run_res = run(["exec", "--json", "--skip-git-repo-check",
                           "--sandbox", "danger-full-access",
                           "run the shell command codemonkey_tool_test"],
                          env, tmp)
            thread = ""
            for line in run_res.stdout.splitlines():
                if line.startswith("{") and '"thread.started"' in line:
                    thread = json.loads(line).get("thread_id", "")
                    break
            print(f"# run exit {run_res.returncode}, thread {thread!r}")
            jdir = home / ".codemonkey" / "journal"
            if not thread:
                failures.append("no thread.started line from the run")
            elif not jdir.exists() or not list(jdir.glob("*.jsonl")):
                failures.append("the run journaled nothing")

            # 2. pack it through the CLI
            pack_path = tmp / "pack.json"
            p = run(["evidence", "pack", thread, "--out", str(pack_path)], env, tmp)
            print(f"$ codemonkey evidence pack {thread} --out pack.json")
            print(f"[exit {p.returncode}] {p.stdout.strip()} {p.stderr.strip()}")
            if p.returncode != 0 or not pack_path.exists():
                failures.append(f"pack failed: exit {p.returncode} {p.stderr}")

            # 3. verify it — must pass
            v = run(["evidence", "verify", str(pack_path)], env, tmp)
            print(f"$ codemonkey evidence verify pack.json")
            print(f"[exit {v.returncode}] {v.stdout.strip()} {v.stderr.strip()}")
            if v.returncode != 0:
                failures.append(f"a fresh pack did not verify: {v.stdout}")
            if "PACK VERIFIES" not in v.stdout:
                failures.append("verify did not report PACK VERIFIES")

            # 4. TAMPER and show it go red — the whole point of the chain
            doc = json.loads(pack_path.read_text())
            if doc["records"]:
                doc["records"][0]["tool"] = "not-the-real-tool"
                pack_path.write_text(json.dumps(doc))
                t = run(["evidence", "verify", str(pack_path)], env, tmp)
                print(f"$ (tampered record 0) codemonkey evidence verify pack.json")
                print(f"[exit {t.returncode}] {t.stdout.strip()}")
                if t.returncode == 0:
                    failures.append("a TAMPERED pack still verified")
                if "chain broken" not in t.stderr:
                    failures.append(f"no chain-broken reason: {t.stderr!r}")

    if failures:
        print("\nPROBE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nPROBE OK: pack → verify green, tampered pack → RED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
