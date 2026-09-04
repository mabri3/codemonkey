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
    assert res["ok"] is True and res["kind"] == "ok"
    assert res["path"][0] == "exec.py"
    assert res["path"][-1] == "loop.py"
    assert "run_turns" in res["path"]


def test_graph_path_unresolved_endpoint_is_no_path_not_error(tmp_path):
    # 74F5: unresolved endpoints on a usable graph = successful no-match.
    _write_graph(tmp_path)
    from codemonkey.tools.graph import graph_path_lookup

    res = graph_path_lookup(tmp_path, "exec.py", "does-not-exist")
    assert res["ok"] is True and res["kind"] == "no_path"
    assert "no path" in res["error"]


def test_graph_explain(tmp_path):
    _write_graph(tmp_path)
    from codemonkey.tools import dispatch

    res = dispatch("graph_explain", {"name": "run_turns"}, _Ctx(tmp_path))
    assert res.ok is True
    assert "run_turns" in res.output


# ---------------- 74F4: single-file fallback layout loads ----------------

def test_f4_single_file_layout_loads_clean(tmp_path):
    # graph.json directly at workspace root (find_graph_dir's file fallback):
    # must answer from the graph, with NO stale marker and NO empty answer.
    data = {
        "nodes": [{"id": "run_turns", "src": "src/codemonkey/loop.py",
                   "label": "run_turns"}],
        "edges": [{"source": "exec.py", "target": "run_turns",
                   "relation": "calls"}],
    }
    (tmp_path / "graph.json").write_text(json.dumps(data))
    from codemonkey.tools import dispatch

    res = dispatch("graph_query", {"symbol": "run_turns"}, _Ctx(tmp_path))
    assert res.ok is True, res.output
    assert "run_turns" in res.output
    assert "exec.py" in res.output            # edge endpoint printed
    assert "[stale:" not in res.output        # staleness must not misfire


def test_f4_single_file_layout_bfs_path(tmp_path):
    data = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [{"source": "a", "target": "b", "relation": "x"},
                  {"source": "b", "target": "c", "relation": "x"}],
    }
    (tmp_path / "graph.json").write_text(json.dumps(data))
    from codemonkey.tools.graph import graph_path_lookup

    res = graph_path_lookup(tmp_path, "a", "c")
    assert res["kind"] == "ok" and res["path"] == ["a", "b", "c"]


# ---------------- 74F5: uniform no-match contract ----------------

def test_f5_no_match_is_ok_true_query_tool(tmp_path):
    # graph_query: well-formed query, zero hits -> ok=True + explicit line.
    _write_graph(tmp_path)
    from codemonkey.tools import dispatch

    res = dispatch("graph_query", {"symbol": "zzz_nonexistent"}, _Ctx(tmp_path))
    assert res.ok is True
    assert "no node matches" in res.output


def test_f5_no_match_is_ok_true_explain_tool(tmp_path):
    # graph_explain: same contract (was ok=False before 74F5).
    _write_graph(tmp_path)
    from codemonkey.tools import dispatch

    res = dispatch("graph_explain", {"name": "zzz_nonexistent"}, _Ctx(tmp_path))
    assert res.ok is True
    assert "no node matches" in res.output


def test_f5_no_match_is_ok_true_path_tool(tmp_path):
    # graph_path: connectable-graph miss -> no_path answer, ok=True.
    _write_graph(tmp_path)
    from codemonkey.tools import dispatch

    res = dispatch("graph_path", {"from": "run_turns",
                                  "to": "zzz_nonexistent"}, _Ctx(tmp_path))
    assert res.ok is True
    assert "no path" in res.output


# ---------------- 74F6: CLI graph exit codes + no unused load ----------------

def test_f6_cli_graph_exit_codes(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from codemonkey import cli as cli_mod
    from pathlib import Path as _P

    _write_graph(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    # 0 = match found
    r0 = runner.invoke(cli_mod.app, ["graph", "run_turns"])
    assert r0.exit_code == 0
    # 1 = no match (documented for scripting callers)
    r1 = runner.invoke(cli_mod.app, ["graph", "nosuchsymbol_zzz"])
    assert r1.exit_code == 1, r1.output
    # 2 = no usable graph
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    r2 = runner.invoke(cli_mod.app, ["graph", "run_turns"])
    assert r2.exit_code == 2


def test_f6_cli_graph_to_path_skips_unused_load(tmp_path, monkeypatch):
    # The --to branch must not load the graph twice (74F6): patch load_graph
    # to explode and prove the --to path never calls it directly.
    import codemonkey.cli as cli_mod
    from typer.testing import CliRunner

    _write_graph(tmp_path)
    monkeypatch.chdir(tmp_path)

    import codemonkey.graphquery as gq_mod
    called = {"n": 0}
    real_load = gq_mod.load_graph
    def spy_load(graph_dir):
        called["n"] += 1
        return real_load(graph_dir)
    monkeypatch.setattr(gq_mod, "load_graph", spy_load)
    runner = CliRunner()
    r = runner.invoke(cli_mod.app, ["graph", "exec.py", "--to", "loop.py"])
    assert r.exit_code == 0, r.output
    assert "path: exec.py -> run_turns -> loop.py" in r.output
    # exactly ONE load: inside graph_path_lookup — the CLI's own pre-load is
    # gone from the --to branch (74F6).
    assert called["n"] == 1


def test_f6_cli_help_documents_exit_codes():
    from typer.testing import CliRunner
    from codemonkey import cli as cli_mod

    runner = CliRunner()
    r = runner.invoke(cli_mod.app, ["graph", "--help"])
    assert r.exit_code == 0
    assert "Exit codes" in r.output
    for code in ("0 =", "1 =", "2 ="):
        assert code in r.output
