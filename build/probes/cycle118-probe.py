"""CYCLE 118 R-I probe — propagation: spill sidecars + compaction records.

(a) spill a tainted output → sidecar; read it back (add-dir'd spill root) →
    record `spill`; clean spill → no sidecar, read-back `outside_read`;
(b) a compaction that drops tainted-derived messages journals
    `taint.propagation` (run_tainted true, counts) and the tracker stays
    tainted; a clean run compacts with NO record.

Usage:  uv run python build/probes/cycle118-probe.py
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


class T:
    def __init__(self, c):
        self.content = c
        self.usage = {}
        self.tool_calls = []


class P:
    protocol = "openai"

    def __init__(self, script):
        self.script = script
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        return T(self.script[self.n - 1] if self.n - 1 < len(self.script)
                 else "done")


def run(ws, thread, script, **kw):
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    ctx = ToolContext(workdir=ws, sandbox="workspace-write", timeout=30,
                      extra={"config": {}, "session_id": thread, "run_id": "r"},
                      **{k: v for k, v in kw.items() if k == "add_dirs"})
    rt_kw = {k: v for k, v in kw.items() if k != "add_dirs"}
    run_turns(P(script), "go", ctx, tool_protocol="prompt", max_turns=8,
              memory_enabled=False, journal_thread=thread, journal_run="j",
              **rt_kw)
    return ctx


def main() -> int:
    from codemonkey import journal
    from codemonkey.spill import spill_dir, taint_for_path, truncate_with_spill
    from codemonkey.strategies.compaction import SlidingWindowCompaction

    tmp = Path(tempfile.mkdtemp(prefix="cm118-"))
    os.environ["HOME"] = str(tmp / ".home")
    ws = tmp / "ws"
    ws.mkdir()

    print("--- a. spill sidecar + read-back ---")
    marker = truncate_with_spill("z" * 5000, 400, tool="shell",
                                 taint={"sources": ["web_fetch"], "tainted": True})
    path = [m for m in marker.split() if "spill" in m and m.endswith(".txt")][0]
    clean = truncate_with_spill("q" * 5000, 400, tool="shell")
    cpath = [m for m in clean.split() if "spill" in m and m.endswith(".txt")][0]
    print(f"    tainted sidecar: {taint_for_path(path)}")
    check("tainted spill has a tainted sidecar",
          taint_for_path(path)["tainted"] is True)
    check("clean spill has NO sidecar", taint_for_path(cpath) is None)

    run(ws, "p118a", [
        "TOOL_CALL: " + json.dumps({"name": "read_file", "arguments": {"path": path}}),
        "TOOL_CALL: " + json.dumps({"name": "read_file", "arguments": {"path": cpath}}),
        "stopped"], add_dirs=[spill_dir()])
    recs = [r for r in journal.read_thread("p118a") if r.get("type") == "outcome"]
    print(f"    tainted read-back: {recs[0]['taint_sources']}")
    print(f"    clean   read-back: {recs[1]['taint_sources']}")
    check("tainted spill read-back attributes `spill`",
          recs[0]["taint_sources"] == ["spill"])
    check("clean spill read-back is not laundered into `spill`",
          recs[1]["taint_sources"] == ["outside_read"])

    print("--- b. compaction propagation ---")
    ws2 = tmp / "ws2"
    ws2.mkdir()
    ctx = run(ws2, "p118b", [
        "TOOL_CALL: " + json.dumps({"name": "shell",
                                    "arguments": {"command": "echo " + "A" * 4000}}),
        "TOOL_CALL: " + json.dumps({"name": "shell",
                                    "arguments": {"command": "echo small"}}),
        "stopped"], context_limit=800, compaction=SlidingWindowCompaction(keep=2))
    prop = [r for r in journal.read_thread("p118b")
            if r.get("type") == "taint.propagation"]
    print(f"    propagation records: {len(prop)}; first: "
          f"{ {k: prop[0].get(k) for k in ('run_tainted', 'messages_tainted_derived', 'dropped')} if prop else None }")
    check("propagation journaled with counts",
          bool(prop) and prop[0]["run_tainted"] is True
          and prop[0]["messages_tainted_derived"] >= 1)
    check("sticky: tracker still tainted after the rewrite",
          bool(ctx.extra["taint"].tainted))

    ws3 = tmp / "ws3"
    ws3.mkdir()
    (ws3 / "big.txt").write_text("B" * 6000)
    ctx3 = run(ws3, "p118c", [
        "TOOL_CALL: " + json.dumps({"name": "read_file", "arguments": {"path": "big.txt"}}),
        "TOOL_CALL: " + json.dumps({"name": "read_file", "arguments": {"path": "big.txt"}}),
        "stopped"], context_limit=800, compaction=SlidingWindowCompaction(keep=2))
    prop3 = [r for r in journal.read_thread("p118c")
             if r.get("type") == "taint.propagation"]
    check("clean twin compacts with NO propagation record (+ tracker clean)",
          prop3 == [] and ctx3.extra["taint"].tainted is False)

    print()
    print("CYCLE118 PROBE: " + ("PASS" if not FAIL else "FAIL"))
    return FAIL


if __name__ == "__main__":
    raise SystemExit(main())
