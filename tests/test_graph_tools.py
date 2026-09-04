"""Cycle 74 (loop 38): graph tools wired into the registry — R-I entry-point work.

Unit coverage here locks the registry/sandbox/staleness/honesty contracts; the
cycle's verify probe additionally drives `codemonkey graph` (CLI) and, live,
`exec` with a real graph_query tool call.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from codemonkey import graphquery
from codemonkey.sandbox import ToolContext, can


# ---------------- registry + sandbox classification ----------------

def test_graph_tools_registered():
    from codemonkey import tools

    for name in ("graph_query", "graph_path", "graph_explain"):
        assert name in tools._MODULES, name
        assert name in tools.SPECS, name
        assert name in tools.PARAMS, name


def test_graph_tools_are_read_only_allowed():
    for name in ("graph_query", "graph_path", "graph_explain"):
        assert can(name, "read-only") is True


def test_unknown_still_denied_readonly():
    assert can("shell", "read-only") is False


# ---------------- honesty: missing graph ----------------

class _Ctx(ToolContext):
    def __init__(self, workdir):
        super().__init__(workdir=Path(workdir), sandbox="read-only", timeout=30)


def _write_graph(tmp_path: Path, *, mtime: float | None = None):
    gdir = tmp_path / "graphify-out"
    gdir.mkdir(exist_ok=True)
    data = {
        "nodes": [
            {"id": "run_turns", "src": "src/codemonkey/loop.py", "label": "run_turns"},
            {"id": "loop.py", "src": "src/codemonkey/loop.py", "label": "loop.py"},
            {"id": "exec.py", "src": "src/codemonkey/exec.py", "label": "exec.py"},
        ],
        "edges": [
            {"source": "exec.py", "target": "run_turns", "relation": "calls"},
            {"source": "run_turns", "target": "loop.py", "relation": "member-of"},
        ],
    }
    p = gdir / "graph.json"
    p.write_text(json.dumps(data))
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return gdir


def test_graph_query_missing_graph_is_honest(tmp_path):
    from codemonkey.tools import dispatch

    res = dispatch("graph_query", {"symbol": "run_turns"}, _Ctx(tmp_path))
    assert res.ok is False
    assert "no graphify-out" in res.output


# ---------------- query + staleness ----------------

def test_graph_query_returns_matches_and_edges(tmp_path):
    _write_graph(tmp_path)
    from codemonkey.tools import dispatch

    res = dispatch("graph_query", {"symbol": "run_turns"}, _Ctx(tmp_path))
    assert res.ok is True, res.output
    assert "run_turns" in res.output
    assert "exec.py" in res.output  # edge endpoint printed


def test_graph_query_stale_marker_in_band(tmp_path):
    # graph older than HEAD -> tool output carries [stale: ...], never silent.
    # Fake "HEAD is new" by pre-checking the marker with a mtimes far in the past.
    _write_graph(tmp_path, mtime=time.time() - 86400)
    # The staleness check compares against the last commit of the WORKDIR; the
    # tmp dir has no commits, so _check_staleness returns "" (undeterminable).
    # Drive the checker directly with a git repo to prove both directions.
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "f.txt").write_text("x")
    def _git(*a):
        subprocess.run(["git", "-C", str(repo), *a], capture_output=True, check=True)
    _git("init", "-q")
    _git("config", "user.name", "t")
    _git("config", "user.email", "t@t")
    _git("add", "-A")
    _git("commit", "-qm", "init")
    _write_graph(repo, mtime=time.time() - 86400)  # a day older than HEAD
    from codemonkey.tools.graph import _check_staleness

    marker = _check_staleness(repo / "graphify-out", repo)
    assert marker.startswith("[stale:")
    # fresh graph -> no marker
    _write_graph(repo)  # now mtime
    assert _check_staleness(repo / "graphify-out", repo) == ""


def test_graph_path_lookup(tmp_path):
    _write_graph(tmp_path)
    from codemonkey.tools.graph import graph_path_lookup

    res = graph_path_lookup(tmp_path, "exec.py", "loop.py")
    assert res["ok"] is True
    assert res["path"][0] == "exec.py"
    assert res["path"][-1] == "loop.py"
    assert "run_turns" in res["path"]


def test_graph_path_unresolved_endpoint_honest(tmp_path):
    _write_graph(tmp_path)
    from codemonkey.tools.graph import graph_path_lookup

    res = graph_path_lookup(tmp_path, "exec.py", "does-not-exist")
    assert res["ok"] is False
    assert "unresolved" in res["error"]


def test_graph_explain(tmp_path):
    _write_graph(tmp_path)
    from codemonkey.tools import dispatch

    res = dispatch("graph_explain", {"name": "run_turns"}, _Ctx(tmp_path))
    assert res.ok is True
    assert "run_turns" in res.output
