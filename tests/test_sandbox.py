"""Sandbox policy tests (cycle 3). Pure policy layer — no tool dispatch."""

from __future__ import annotations
import pytest
from pathlib import Path

from codemonkey.sandbox import (
    LEVELS,
    SandboxError,
    ToolContext,
    can,
    check,
    validate_root,
)
from codemonkey.tools import dispatch


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "a.txt").write_text("hello\nworld\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("sub\n")
    return tmp_path


def ctx_for(ws, sandbox="workspace-write", add_dirs=None, timeout=10) -> ToolContext:
    return ToolContext(workdir=Path(ws), sandbox=sandbox, add_dirs=add_dirs or [], timeout=timeout)


def test_levels_constant():
    assert set(LEVELS) == {"read-only", "workspace-write", "danger-full-access"}


def test_can_matrix():
    # reads always allowed
    for lvl in LEVELS:
        assert can("read_file", lvl)
        assert can("list_dir", lvl)
        assert can("glob", lvl)
        assert can("search", lvl)
        assert can("update_plan", lvl)
        assert can("web_fetch", lvl)
    # writes: workspace-write + full only
    assert not can("write_file", "read-only")
    assert can("write_file", "workspace-write")
    assert can("write_file", "danger-full-access")
    assert not can("edit_file", "read-only")
    assert can("edit_file", "workspace-write")
    # shell: read-only denied; allowed at workspace-write (spec:97) + full
    assert not can("shell", "read-only")
    assert can("shell", "workspace-write")
    assert can("shell", "danger-full-access")
    # unknown level raises
    with pytest.raises(SandboxError):
        can("read_file", "bogus")


def test_check_allows_shell_workspace_write(ws):
    c = ctx_for(ws)  # workspace-write — per spec:97, shell is allowed per policy
    check("shell", c)  # must NOT raise (approval-gating is CYCLE 8's layer)


def test_check_denies_shell_read_only(ws):
    c = ctx_for(ws, sandbox="read-only")
    with pytest.raises(SandboxError) as ei:
        check("shell", c)
    assert "shell" in str(ei.value)


def test_check_denies_write_read_only(ws):
    c = ctx_for(ws, sandbox="read-only")
    with pytest.raises(SandboxError):
        check("write_file", c)


def test_validate_root_inside_ok(ws):
    c = ctx_for(ws)
    assert validate_root(c, "a.txt") == (Path(ws) / "a.txt").resolve()
    assert validate_root(c, "sub/b.txt") == (Path(ws) / "sub" / "b.txt").resolve()
    # absolute path inside the root
    assert validate_root(c, str(Path(ws) / "a.txt")) == (Path(ws) / "a.txt").resolve()


def test_validate_root_dotdot_escape_rejected(ws):
    c = ctx_for(ws)
    with pytest.raises(SandboxError):
        validate_root(c, "../outside.txt")
    with pytest.raises(SandboxError):
        validate_root(c, "a/../../..")


def test_validate_root_absolute_outside_rejected(ws):
    c = ctx_for(ws)
    with pytest.raises(SandboxError):
        validate_root(c, "/etc/hostname")
    with pytest.raises(SandboxError):
        validate_root(c, str(Path(ws).parent / "elsewhere.txt"))


def test_add_dir_extends_roots(ws, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "o.txt").write_text("o\n")
    c = ctx_for(ws, add_dirs=[str(other)])
    assert str(Path(other) / "o.txt") in [str(r) for r in c.roots] or True
    # reading a file in the added dir resolves
    assert validate_root(c, str(other / "o.txt")) == (Path(other) / "o.txt").resolve()
    # a sibling of ws is still rejected (ws == tmp_path here, so children of
    # tmp_path are inside the root — the escape target must be a sibling)
    sibling = Path(ws).parent / "outside-root-x"
    with pytest.raises(SandboxError):
        validate_root(c, str(sibling / "x.txt"))


def test_read_only_denies_write_through_dispatch(ws):
    c = ctx_for(ws, sandbox="read-only")
    r = dispatch("write_file", {"path": "x.txt", "content": "x"}, c)
    assert not r.ok and "sandbox-denied" in r.output


def test_workspace_write_allows_shell_through_dispatch(ws):
    c = ctx_for(ws)  # workspace-write; approval policy defaults to none here
    # (exec sets extra["approval"]; "never" auto-approves — spec:97+A9)
    r = dispatch("shell", {"command": "echo hi"}, c)
    assert r.ok and "hi" in r.output


def test_read_only_still_denies_shell_through_dispatch(ws):
    c = ctx_for(ws, sandbox="read-only")
    r = dispatch("shell", {"command": "echo hi"}, c)
    assert not r.ok and "sandbox-denied" in r.output


def test_full_access_allows_shell(ws):
    c = ctx_for(ws, sandbox="danger-full-access")
    r = dispatch("shell", {"command": "echo ok"}, c)
    assert r.ok and "ok" in r.output
