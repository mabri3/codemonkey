"""Cycle 98 (loop 41): graph-grounded impact analysis vs search-driven.

The charter probe asked for callers the graph touches that search misses.

**98F1 correction.** C98 originally recorded the premise as INVERTED —
"`calls` edges are same-file-only, graph_only is empty" — and pinned that
result. It was an artifact of `graphquery.load_graph`, which read only
`data["edges"]` while `graphify-out/graph.json` stores relationships under
`"links"`, so every edge any consumer saw came from per-file AST cache
fragments (same-file by construction). With the loader fixed, this repo's
graph holds 892 cross-file `calls` edges and the fixture yields cross-file
callers. R41-C2 is REOPENED: the graph does know callers.

The pin did its job — it failed the moment the evidence changed. What it
could not do was notice that the evidence was wrong when it was written,
which is why the replacement tests below assert against the graph file's
own content rather than against a remembered number.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from codemonkey import impact as imp_mod

graphify = pytest.mark.skipif(shutil.which("graphify") is None,
                              reason="graphify binary not on PATH")


def _fixture(root):
    (root / "m.py").write_text("def target(x):\n    return x * 2\n")
    (root / "direct.py").write_text(
        "from m import target\n\ndef run_direct():\n    return target(21)\n")
    (root / "alias.py").write_text(
        "from m import target as t\n\ndef run_alias():\n    return t(21)\n")
    (root / "dynamic.py").write_text(
        'import m\nname = "target"\n\ndef run_dynamic():\n'
        '    return getattr(m, name)(21)\n')
    (root / "noise.py").write_text(
        "# target throughput goals\n\ndef retarget():\n    return 0\n")


@graphify
def test_compare_on_real_extract(tmp_path):
    _fixture(tmp_path)
    subprocess.run(["graphify", "."], cwd=tmp_path, check=True,
                   capture_output=True, timeout=240)
    cmp = imp_mod.compare(tmp_path, "m", "target")
    assert set(cmp["graph_importers"]) == {"direct.py", "alias.py",
                                           "dynamic.py"}
    assert cmp["graph_importers"]["direct.py"] == ["imports_from"]
    assert cmp["graph_importers"]["alias.py"] == ["imports_from"]
    assert cmp["graph_importers"]["dynamic.py"] == ["imports"]
    assert {"direct.py", "alias.py", "dynamic.py"} <= set(cmp["search_files"])
    assert "noise.py" in cmp["search_files"]  # comment + substring hit
    assert "noise.py" not in cmp["graph_files"]


@graphify
def test_cross_file_callers_are_observable(tmp_path):
    """98F1: replaces test_graph_only_empty_pinned, which pinned a loader
    artifact. The extractor DOES resolve cross-file calls; the fixture's
    direct and alias importers are callers, and the loader must show them."""
    _fixture(tmp_path)
    subprocess.run(["graphify", "."], cwd=tmp_path, check=True,
                   capture_output=True, timeout=240)
    cmp = imp_mod.compare(tmp_path, "m", "target")
    assert set(cmp["graph_callers"]) >= {"direct.py", "alias.py"}, \
        cmp["graph_callers"]
    # noise.py never becomes a caller: precision is the graph's real edge
    assert "noise.py" not in cmp["graph_callers"]


def test_loader_reads_links_not_only_edges(tmp_path):
    """98F1 root cause: graphify writes `links`; only the AST cache writes
    `edges`. Reading one key drops the whole current graph."""
    import json

    from codemonkey.graphquery import load_graph

    gdir = tmp_path / "graphify-out"
    gdir.mkdir()
    (gdir / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "a", "source_file": "a.py"},
                  {"id": "b", "source_file": "b.py"}],
        "links": [{"relation": "calls", "source": "a", "target": "b",
                   "source_file": "a.py"}]}))
    g = load_graph(gdir)
    assert len(g["edges"]) == 1, "the `links` key must be read"
    assert g["edges"][0]["relation"] == "calls"


def test_loader_ignores_backups_and_cache(tmp_path):
    """98F1 second defect: rglob swept dated backup snapshots and the
    per-file AST cache, so deleted modules were served as live."""
    import json

    from codemonkey.graphquery import load_graph

    gdir = tmp_path / "graphify-out"
    (gdir / "cache" / "ast" / "v1").mkdir(parents=True)
    (gdir / "2026-01-01").mkdir(parents=True)
    (gdir / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "live", "source_file": "live.py"}],
        "links": [{"relation": "calls", "source": "live", "target": "live"}]}))
    # a stale snapshot naming a module that no longer exists (the R-L case)
    (gdir / "2026-01-01" / "graph.json").write_text(json.dumps({
        "nodes": [{"id": "deleted", "source_file": "deleted.py"}],
        "links": [{"relation": "calls", "source": "deleted",
                   "target": "deleted"}]}))
    (gdir / "cache" / "ast" / "v1" / "frag.json").write_text(json.dumps({
        "nodes": [{"id": "frag", "source_file": "frag.py"}],
        "edges": [{"relation": "calls", "source": "frag", "target": "frag"}]}))
    g = load_graph(gdir)
    assert set(g["nodes"]) == {"live"}, set(g["nodes"])
    assert len(g["edges"]) == 1


def test_missing_graph_raises_honestly(tmp_path):
    with pytest.raises(LookupError, match="no graphify-out"):
        imp_mod.compare(tmp_path, "m", "target")


def test_search_files_uses_real_tool(tmp_path):
    (tmp_path / "a.py").write_text("target = 1\n")
    found = imp_mod.search_files(tmp_path, "target")
    assert found == {"a.py"}


def test_path_endpoint_resolution_prefers_exact_match():
    """98F2: graph_query's max_results caps EDGES, not matches, so
    next(iter(matches)) returned an arbitrary substring hit — for
    `run_turns` a test function — and a one-hop path reported no_path."""
    import json

    from codemonkey.tools.graph import graph_path_lookup

    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as td:
        gdir = _P(td) / "graphify-out"
        gdir.mkdir()
        (gdir / "graph.json").write_text(json.dumps({
            "nodes": [
                # a substring hit that sorts FIRST and is not the target
                {"id": "tests_test_x_calls_run_turns", "label": "test_x()"},
                {"id": "run_turns", "label": "run_turns()"},
                {"id": "estimate_tokens", "label": "estimate_tokens()"}],
            "links": [{"relation": "calls", "source": "run_turns",
                       "target": "estimate_tokens"}]}))
        res = graph_path_lookup(td, "run_turns", "estimate_tokens", max_depth=6)
    assert res["kind"] == "ok", res
    assert res["path"][0] == "run_turns", res["path"]
