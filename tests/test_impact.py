"""Cycle 98 (loop 41): graph-grounded impact analysis vs search-driven.

The charter probe asked for callers the graph touches that search misses.
Measurement (real `graphify` extract + real search tool, fixture below)
says the premise is inverted on this extractor: `calls` edges are
same-file-only, so graph_only is EMPTY and search_only is the NOISE the
graph correctly excludes. That inversion is pinned here — if a future
extractor emits cross-file calls, test_graph_only_empty FAILS and reopens
R41-C2 instead of passing silently (R-L doing its job on our own research).
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
def test_graph_only_empty_pinned(tmp_path):
    """R-L pin: no cross-file callers exist in fresh extracts. If this
    fails, the extractor learned cross-file calls — reopen R41-C2."""
    _fixture(tmp_path)
    subprocess.run(["graphify", "."], cwd=tmp_path, check=True,
                   capture_output=True, timeout=240)
    cmp = imp_mod.compare(tmp_path, "m", "target")
    assert cmp["graph_only"] == [], cmp["graph_only"]
    assert cmp["graph_callers"] == {}, cmp["graph_callers"]


def test_missing_graph_raises_honestly(tmp_path):
    with pytest.raises(LookupError, match="no graphify-out"):
        imp_mod.compare(tmp_path, "m", "target")


def test_search_files_uses_real_tool(tmp_path):
    (tmp_path / "a.py").write_text("target = 1\n")
    found = imp_mod.search_files(tmp_path, "target")
    assert found == {"a.py"}
