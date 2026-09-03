"""Cycle 30 (loop6): tool-result spill.

Verify probe (plan.md): >=6 tests — spill verbatim, marker contains path,
under-budget untouched, prune, read_file slice retrieval, head+tail shape.
"""

from __future__ import annotations

import os

import pytest

from codemonkey.spill import prune, spill, truncate_with_spill


@pytest.fixture()
def spill_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_spill_writes_verbatim(spill_home):
    out = "line1\nline2\nline3\n" * 100
    p = spill(out, tool="shell")
    assert p.read_text() == out
    assert "shell" in p.name


def test_marker_contains_path(spill_home):
    out = "x" * 5000
    result = truncate_with_spill(out, 1000, tool="shell")
    assert "PARTIAL" in result
    # the marker carries a real spill path that exists
    start = result.find("full output saved to ")
    assert start > 0
    path = result[start + len("full output saved to "):].split(" —")[0]
    assert os.path.isfile(path)
    assert open(path).read() == out


def test_under_budget_untouched(spill_home):
    out = "short output"
    assert truncate_with_spill(out, 1000) == out


def test_head_tail_shape(spill_home):
    out = "".join(f"L{i:05d}\n" for i in range(1000))  # 7000 chars
    result = truncate_with_spill(out, 1000, tool="shell")
    assert result.startswith("L00000")          # head preserved
    assert "L00999" in result                    # tail preserved
    assert "PARTIAL" in result and "7000 chars total" in result


def test_prune_removes_old_files(spill_home, monkeypatch):
    p1 = spill("old content", tool="shell")
    # backdate beyond TTL
    old = os.path.getmtime(p1) - 25 * 3600
    os.utime(p1, (old, old))
    spill("fresh content", tool="shell")
    removed = prune(max_age_hours=24)
    assert removed == 1
    assert not p1.exists()


def test_read_file_can_retrieve_slice(spill_home, tmp_path):
    """The model's recovery path: read_file on the spill path."""
    out = "".join(f"L{i:05d}\n" for i in range(2000))
    result = truncate_with_spill(out, 800, tool="search")
    start = result.find("full output saved to ")
    path = result[start + len("full output saved to "):].split(" —")[0]

    from codemonkey.tools.read_file import run as read_file_run
    from codemonkey.sandbox import ToolContext

    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)
    res = read_file_run({"path": path, "offset": 1500, "limit": 5}, ctx)
    assert res.ok, res.output
    assert "L01500" in res.output