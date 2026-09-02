"""Cycle 14 (loop2): checkpoints/rollback.

Verify probe (plan.md): >=5 tests — snapshot before write/edit, restore
byte-identical, --list ordering, no-snapshot for new files, empty restore raises.
"""

from __future__ import annotations

import time

import pytest

from codemonkey import checkpoints as cp_mod
from codemonkey.sandbox import ToolContext
from codemonkey.tools import dispatch


def _ctx_of(tmp):
    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    cpdir = tmp_path / "cps"
    monkeypatch.setattr(cp_mod, "checkpoints_dir", lambda: cpdir)
    return {"tmp": tmp_path, "cpdir": cpdir}


def test_snapshot_before_write(env):
    tmp = env["tmp"]
    f = tmp / "a.txt"
    f.write_text("version one\n")
    r = dispatch("write_file", {"path": "a.txt", "content": "version two\n"}, _ctx_of(tmp))
    assert r.ok
    cps = cp_mod.list_checkpoints()
    assert len(cps) == 1
    assert cps[0]["files"] == ["a.txt"]
    snap = cps[0]["dir"]
    assert (snap / "a.txt").read_text() == "version one\n"   # PRIOR content kept


def test_restore_byte_identical(env):
    tmp = env["tmp"]
    f = tmp / "b.txt"
    prior = b"binary-ish \x00\x01 prior"
    f.write_bytes(prior)
    dispatch("write_file", {"path": "b.txt", "content": "clobbered"}, _ctx_of(tmp))
    assert f.read_text() == "clobbered"
    result = cp_mod.restore_latest(tmp)
    assert result["restored"] == ["b.txt"]
    assert f.read_bytes() == prior


def test_list_newest_first(env):
    tmp = env["tmp"]
    f = tmp / "c.txt"
    f.write_text("v1")
    dispatch("write_file", {"path": "c.txt", "content": "v2"}, _ctx_of(tmp))
    time.sleep(0.02)
    f.write_text("v3")
    dispatch("write_file", {"path": "c.txt", "content": "v4"}, _ctx_of(tmp))
    cps = cp_mod.list_checkpoints()
    assert len(cps) == 2
    assert cps[0]["ts"] >= cps[1]["ts"]
    assert (cps[0]["dir"] / "c.txt").read_text() == "v3"   # newest = state before last write
    assert (cps[1]["dir"] / "c.txt").read_text() == "v1"


def test_edit_file_snapshots_too(env):
    tmp = env["tmp"]
    f = tmp / "e.py"
    f.write_text("x = 1\n")
    dispatch("edit_file", {"path": "e.py", "old_string": "x = 1", "new_string": "x = 2"}, _ctx_of(tmp))
    assert f.read_text() == "x = 2\n"
    result = cp_mod.restore_latest(tmp)
    assert result["restored"] == ["e.py"]
    assert f.read_text() == "x = 1\n"


def test_new_file_write_makes_no_snapshot(env):
    tmp = env["tmp"]
    dispatch("write_file", {"path": "fresh.txt", "content": "brand new"}, _ctx_of(tmp))
    dispatch("write_file", {"path": "sub/other.txt", "content": "x"}, _ctx_of(tmp))
    cps = cp_mod.list_checkpoints()
    for c in cps:
        assert "fresh.txt" not in c["files"]
        assert "other.txt" not in c["files"]


def test_no_checkpoints_restore_raises(env):
    with pytest.raises(LookupError):
        cp_mod.restore_latest(env["tmp"])
