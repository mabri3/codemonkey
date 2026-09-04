"""R28: graph-grounded retrieval."""

from __future__ import annotations

import json

import pytest

from codemonkey.graphquery import (find_graph_dir, graph_query, load_graph)


@pytest.fixture()
def grepo(tmp_path):
    gdir = tmp_path / "graphify-out"
    gdir.mkdir()
    (gdir / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "codemonkey/exec.py::run_exec", "name": "run_exec",
                   "kind": "function"},
                  {"id": "codemonkey/loop.py::run_turns", "name": "run_turns",
                   "kind": "function"}],
        "edges": [{"source": "codemonkey/exec.py::run_exec",
                   "target": "codemonkey/loop.py::run_turns",
                   "kind": "calls"}],
    }))
    return tmp_path


def test_find_graph_dir(grepo):
    assert find_graph_dir(grepo) == grepo / "graphify-out"


def test_absent_graph_is_honest(tmp_path):
    assert find_graph_dir(tmp_path) is None
    assert load_graph(tmp_path) == {"nodes": {}, "edges": []}


def test_load_graph_merges(grepo):
    g = load_graph(grepo / "graphify-out")
    assert len(g["nodes"]) == 2 and len(g["edges"]) == 1


def test_pinned_symbol_lookup(grepo):
    g = load_graph(grepo / "graphify-out")
    res = graph_query(g, "run_exec")
    assert "codemonkey/exec.py::run_exec" in res["matches"]
    assert res["edges"]


def test_no_match_empty(grepo):
    g = load_graph(grepo / "graphify-out")
    res = graph_query(g, "nonexistent")
    assert res["matches"] == {} and res["edges"] == []
