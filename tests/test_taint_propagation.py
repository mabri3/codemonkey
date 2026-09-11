"""loop49 cycle 118 — propagation: taint survives compaction and a spill
round-trip; sticky until a new run.

Claims pinned:

* a spill of untrusted-derived output writes a SIDECAR; reading it back
  (add-dir'd spill root) attributes `spill` — the rewrite onto disk is not a
  laundering step;
* a CLEAN spill has no sidecar and its read-back is not marked `spill`
  (negative control — the mechanism can tell the difference);
* a compaction that drops tainted-derived messages journals
  `taint.propagation` with the counts, and the run tracker stays tainted
  (rewrites never clear taint);
* a clean run compacts with NO propagation record.
"""

from __future__ import annotations

import json

from codemonkey import journal
from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext
from codemonkey.spill import spill_dir, taint_for_path, truncate_with_spill
from codemonkey.strategies.compaction import SlidingWindowCompaction


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


def test_spill_sidecar_and_read_back_attribution(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    tainted = {"sources": ["web_fetch"], "tainted": True}
    marker = truncate_with_spill("z" * 5000, 400, tool="shell", taint=tainted)
    path = None
    for m in marker.split():
        if "spill" in m and m.endswith(".txt"):
            path = m
    assert path, marker[:200]
    assert taint_for_path(path)["tainted"] is True
    assert taint_for_path(path)["sources"] == ["web_fetch"]

    clean = truncate_with_spill("q" * 5000, 400, tool="shell")
    cpath = None
    for m in clean.split():
        if "spill" in m and m.endswith(".txt"):
            cpath = m
    assert taint_for_path(cpath) is None       # clean spill: no sidecar

    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = ToolContext(workdir=ws, sandbox="workspace-write", timeout=30,
                      add_dirs=[spill_dir()],
                      extra={"config": {}, "session_id": "t118", "run_id": "r"})
    script = [
        "TOOL_CALL: " + json.dumps({"name": "read_file",
                                    "arguments": {"path": path}}),
        "TOOL_CALL: " + json.dumps({"name": "read_file",
                                    "arguments": {"path": cpath}}),
        "stopped",
    ]
    run_turns(Prov(script), "go", ctx, tool_protocol="prompt", max_turns=6,
              memory_enabled=False, journal_thread="t118", journal_run="j")
    recs = [r for r in journal.read_thread("t118") if r.get("type") == "outcome"]
    assert recs[0]["taint_sources"] == ["spill"]      # tainted spill read-back
    assert recs[1]["taint_sources"] == ["outside_read"]  # clean spill: just outside
    assert ctx.extra["taint"].tainted is True


def test_compaction_of_tainted_derived_messages_journals_the_propagation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    ws = tmp_path / "ws"
    ws.mkdir()
    ctx = ToolContext(workdir=ws, sandbox="workspace-write", timeout=30,
                      extra={"config": {}, "session_id": "t118c", "run_id": "r"})
    # a shell call (coarse source) with a big output → spans the context
    big = "echo " + "A" * 4000
    script = [
        "TOOL_CALL: " + json.dumps({"name": "shell", "arguments": {"command": big}}),
        "TOOL_CALL: " + json.dumps({"name": "shell", "arguments": {"command": "echo small"}}),
        "TOOL_CALL: " + json.dumps({"name": "shell", "arguments": {"command": "echo small2"}}),
        "stopped",
    ]
    run_turns(Prov(script), "go", ctx, tool_protocol="prompt", max_turns=8,
              memory_enabled=False, journal_thread="t118c", journal_run="j",
              context_limit=800, compaction=SlidingWindowCompaction(keep=2))
    recs = journal.read_thread("t118c")
    prop = [r for r in recs if r.get("type") == "taint.propagation"]
    # every shell output is a source by the coarse rule and the stack keeps
    # exceeding the tiny limit, so compactions (and records) recur — the
    # first record is the pinned claim: tainted-derived messages dropped,
    # run tainted, count recorded.
    assert prop, [r.get("type") for r in recs]
    assert prop[0]["run_tainted"] is True
    assert prop[0]["messages_tainted_derived"] >= 1
    assert prop[0]["dropped"] >= 1
    # STICKY: the run tracker is untouched by the rewrites
    assert ctx.extra["taint"].tainted is True


def test_clean_run_compaction_has_no_propagation_record(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / ".home"))
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "big.txt").write_text("B" * 6000)
    ctx = ToolContext(workdir=ws, sandbox="workspace-write", timeout=30,
                      extra={"config": {}, "session_id": "t118d", "run_id": "r"})
    script = [
        "TOOL_CALL: " + json.dumps({"name": "read_file",
                                    "arguments": {"path": "big.txt"}}),
        "TOOL_CALL: " + json.dumps({"name": "read_file",
                                    "arguments": {"path": "big.txt"}}),
        "TOOL_CALL: " + json.dumps({"name": "read_file",
                                    "arguments": {"path": "big.txt"}}),
        "stopped",
    ]
    run_turns(Prov(script), "go", ctx, tool_protocol="prompt", max_turns=8,
              memory_enabled=False, journal_thread="t118d", journal_run="j",
              context_limit=800, compaction=SlidingWindowCompaction(keep=2))
    recs = journal.read_thread("t118d")
    assert [r for r in recs if r.get("type") == "taint.propagation"] == []
    assert ctx.extra["taint"].tainted is False
