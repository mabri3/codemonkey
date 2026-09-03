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


# -- CYCLE 14F1 (critic-loop8 finding 4) ---------------------------------
# One checkpoint group per TOOL CALL: a multi-file atomic edit used to create
# one group per file, so `undo` restored a single file and left the rest
# modified — a torn undo of an "atomic" change.

def test_batch_edit_makes_one_checkpoint_group(env):
    tmp = env["tmp"]
    (tmp / "m1.txt").write_text("one\n")
    (tmp / "m2.txt").write_text("two\n")
    r = dispatch("edit_file", {"edits": [
        {"path": "m1.txt", "search": "one", "replace": "ONE"},
        {"path": "m2.txt", "search": "two", "replace": "TWO"},
    ]}, _ctx_of(tmp))
    assert r.ok, r.output
    cps = cp_mod.list_checkpoints()
    assert len(cps) == 1
    assert sorted(cps[0]["files"]) == ["m1.txt", "m2.txt"]


def test_undo_restores_every_file_of_a_batch(env):
    tmp = env["tmp"]
    (tmp / "m1.txt").write_text("one\n")
    (tmp / "m2.txt").write_text("two\n")
    dispatch("edit_file", {"edits": [
        {"path": "m1.txt", "search": "one", "replace": "ONE"},
        {"path": "m2.txt", "search": "two", "replace": "TWO"},
    ]}, _ctx_of(tmp))
    restored = cp_mod.restore_latest(tmp)["restored"]
    assert sorted(restored) == ["m1.txt", "m2.txt"]
    assert (tmp / "m1.txt").read_text() == "one\n"
    assert (tmp / "m2.txt").read_text() == "two\n"


def test_separate_calls_stay_separate_groups(env):
    tmp = env["tmp"]
    (tmp / "s1.txt").write_text("a\n")
    (tmp / "s2.txt").write_text("b\n")
    dispatch("write_file", {"path": "s1.txt", "content": "A\n"}, _ctx_of(tmp))
    time.sleep(0.02)
    dispatch("write_file", {"path": "s2.txt", "content": "B\n"}, _ctx_of(tmp))
    cps = cp_mod.list_checkpoints()
    assert [c["files"] for c in cps] == [["s2.txt"], ["s1.txt"]]


# -- CYCLE 14F2 (critic-loop8 finding 5) ---------------------------------
# Checkpoints live in one global dir and carried no workspace identity, so
# `codemonkey undo` in repo B restored repo A's files into B.

def test_other_workspace_checkpoint_is_not_listed(env):
    tmp = env["tmp"]
    other = tmp / "other_repo"
    other.mkdir()
    (other / "x.txt").write_text("theirs\n")
    dispatch("write_file", {"path": "x.txt", "content": "changed\n"}, _ctx_of(other))
    mine = tmp / "my_repo"
    mine.mkdir()
    assert cp_mod.list_checkpoints(workdir=other)  # visible where it was taken
    assert cp_mod.list_checkpoints(workdir=mine) == []


def test_undo_in_another_workspace_refuses(env):
    tmp = env["tmp"]
    other = tmp / "other_repo"
    other.mkdir()
    (other / "x.txt").write_text("theirs\n")
    dispatch("write_file", {"path": "x.txt", "content": "changed\n"}, _ctx_of(other))
    mine = tmp / "my_repo"
    mine.mkdir()
    (mine / "x.txt").write_text("mine\n")
    with pytest.raises(LookupError):
        cp_mod.restore_latest(mine)
    assert (mine / "x.txt").read_text() == "mine\n"  # untouched


def test_same_workspace_restore_unchanged(env):
    tmp = env["tmp"]
    repo = tmp / "repo"
    repo.mkdir()
    (repo / "y.txt").write_text("v1\n")
    dispatch("write_file", {"path": "y.txt", "content": "v2\n"}, _ctx_of(repo))
    assert cp_mod.restore_latest(repo)["restored"] == ["y.txt"]
    assert (repo / "y.txt").read_text() == "v1\n"


def test_legacy_group_without_workdir_record_still_restores(env):
    """Groups written before 14F2 carry no marker and stay eligible."""
    tmp = env["tmp"]
    repo = tmp / "legacy"
    repo.mkdir()
    (repo / "z.txt").write_text("new\n")
    cp = cp_mod.new_checkpoint()
    cp.snapshot_file(repo, "z.txt", b"old\n")
    (cp.base / "workdir.txt").unlink()  # simulate a pre-14F2 group
    assert cp_mod.restore_latest(repo)["restored"] == ["z.txt"]
    assert (repo / "z.txt").read_text() == "old\n"
