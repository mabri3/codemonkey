"""CYCLE 109 R-I probe — `context = playbook` through the REAL run path.

Drives run_exec three times against one workspace + store (static, playbook,
playbook with budget 0), captures the system prompt each provider receives,
and asserts the byte-level claims: static is the baseline; playbook adds
exactly the admitted block on a "\n\n" boundary; a budget-0 run is byte-equal
to static with the omission named on stderr.

Usage:  uv run python build/probes/cycle109-probe.py
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


class RecordingProvider:
    protocol = "openai"

    def __init__(self):
        self.systems = []

    def chat(self, messages, system=None, **kw):
        self.systems.append(system or "")
        from codemonkey.providers.base import ChatTurn

        return ChatTurn(content="ok", usage={"total_tokens": 1})


def run(ws: Path, mode: str, budget=None) -> tuple[str, str]:
    import codemonkey.exec as exec_mod

    os.environ["CODEMONKEY_STRATEGY_CONTEXT"] = mode
    if budget is None:
        os.environ.pop("CODEMONKEY_PLAYBOOK_BUDGET", None)
    else:
        os.environ["CODEMONKEY_PLAYBOOK_BUDGET"] = str(budget)
    prov = RecordingProvider()
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    err = io.StringIO()
    try:
        with redirect_stderr(err):
            code = exec_mod.run_exec("Say ok.", cwd=ws, skip_git_repo_check=True,
                                     ephemeral=True, stream_deltas=False,
                                     stdin_cm="")
    finally:
        exec_mod._provider_from_config = orig
    assert code == 0, f"run_exec exit {code}"
    return prov.systems[0], err.getvalue()


def main() -> int:
    from codemonkey import playbook

    tmp = Path(tempfile.mkdtemp(prefix="cm109-"))
    ws = tmp / "ws"
    ws.mkdir()
    os.environ["HOME"] = str(tmp / ".home")

    print("--- 1. static baseline (no store) ---")
    sys_static, _ = run(ws, "static")
    check("static run carries the baseline context block",
          "Working directory" in sys_static)
    check("static carries no playbook header", "Playbook" not in sys_static)

    print("--- 2. playbook mode, empty store -> byte-equal to static ---")
    sys_pb0, err0 = run(ws, "playbook")
    check("byte-equal", sys_pb0 == sys_static)
    print(f"    stderr: {err0.strip()}")

    print("--- 3. quarantined entry -> still byte-equal ---")
    playbook.merge_deltas(ws, [{
        "kind": "strategy", "section": "tools", "text": "quarantined alpha",
        "provenance": {"run_id": "probe", "session_id": "s", "taint_free": True}}])
    sys_pb_q, errq = run(ws, "playbook")
    check("quarantined text absent (byte-equal to static)", sys_pb_q == sys_static)
    check("quarantined text literally absent", "quarantined alpha" not in sys_pb_q)

    print("--- 4. admit TWO entries -> exactly the block added ---")
    eid = playbook.list_entries(ws)[0]["id"]
    playbook.set_status(ws, eid, "admitted", reason="probe")
    playbook.merge_deltas(ws, [{
        "kind": "pitfall", "section": "failures", "text": "delta epsilon",
        "provenance": {"run_id": "probe", "session_id": "s", "taint_free": True}}])
    eid2 = [e["id"] for e in playbook.list_entries(ws)
            if e["text"] == "delta epsilon"][0]
    playbook.set_status(ws, eid2, "admitted", reason="probe")
    sys_pb1, err1 = run(ws, "playbook")
    block = ("## Playbook (admitted)\n"
             "- [strategy/tools] quarantined alpha\n"
             "- [pitfall/failures] delta epsilon")
    check("block present", block in sys_pb1)
    check("removing the block reproduces static byte-for-byte",
          sys_pb1.replace("\n\n" + block, "", 1) == sys_static)
    check("block sits before the tool-protocol section",
          sys_pb1.index("## Playbook") < sys_pb1.index("You have tools."))
    print(f"    stderr: {err1.strip()}")

    print("--- 5. budget 0 -> omitted, byte-equal, and the line says so ---")
    sys_pbz, errz = run(ws, "playbook", budget=0)
    check("byte-equal to static (absence, not a note)", sys_pbz == sys_static)
    check("accounting line names the omission",
          "0/2 entries injected" in errz and "budget: 0 words" in errz
          and "block omitted" in errz)
    print(f"    stderr: {errz.strip()}")

    print("--- 6. partial budget: one fits, one is held ---")
    sys_pbp, errp = run(ws, "playbook", budget=6)
    check("first entry renders, second does not",
          "quarantined alpha" in sys_pbp and "delta epsilon" not in sys_pbp)
    check("line counts 1/2 + 1 held", "1/2 entries injected" in errp and "1 held" in errp)
    print(f"    stderr: {errp.strip()}")

    print("--- 7. revoke the loaded entry -> back to byte-equal ---")
    playbook.revoke(ws, eid)
    playbook.revoke(ws, eid2)
    sys_pbr, _ = run(ws, "playbook")
    check("both revoked -> byte-equal to static", sys_pbr == sys_static)

    print()
    print("CYCLE109 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
