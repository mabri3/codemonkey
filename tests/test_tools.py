"""Tools + sandbox tests (cycle 3). All local; shell tests use safe commands."""

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
from codemonkey.tools import dispatch, names
from codemonkey.tools.base import MAX_OUTPUT


@pytest.fixture
def ws(tmp_path):
    """Workspace with a couple of files; ctx defaults to workspace-write."""
    (tmp_path / "a.txt").write_text("hello\nworld\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("sub content\n")
    return tmp_path


def ctx_for(ws, sandbox="workspace-write", add_dirs=None, timeout=10) -> ToolContext:
    return ToolContext(workdir=Path(ws), sandbox=sandbox, add_dirs=add_dirs or [], timeout=timeout)


# ---------------------------------------------------------------- read_file

def test_read_file_numbered(ws):
    r = dispatch("read_file", {"path": "a.txt"}, ctx_for(ws))
    assert r.ok and r.output.startswith("     1| hello")
    assert "[total_lines=2]" in r.output


def test_read_file_pagination(ws):
    p = ctx_for(ws)
    (p.workdir / "big.txt").write_text("\n".join(f"line{i}" for i in range(50)))
    r = dispatch("read_file", {"path": "big.txt", "offset": 40, "limit": 5}, p)
    assert r.ok and "line39" in r.output and "line43" in r.output
    assert "line44" not in r.output.split("[total_lines")[0].split("\n")[-1]


def test_read_file_out_of_range(ws):
    r = dispatch("read_file", {"path": "a.txt", "offset": 99}, ctx_for(ws))
    assert not r.ok and "out of range" in r.output


# ---------------------------------------------------------------- write_file

def test_write_file_creates_and_overwrites(ws):
    c = ctx_for(ws)
    r = dispatch("write_file", {"path": "new.txt", "content": "x"}, c)
    assert r.ok and (c.workdir / "new.txt").read_text() == "x"
    r = dispatch("write_file", {"path": "new.txt", "content": "yy"}, c)
    assert r.ok and (c.workdir / "new.txt").read_text() == "yy"


def test_write_file_denied_read_only(ws):
    c = ctx_for(ws, sandbox="read-only")
    r = dispatch("write_file", {"path": "x.txt", "content": "x"}, c)
    assert not r.ok and "read-only" in r.output


# ---------------------------------------------------------------- edit_file

def test_edit_file_happy(ws):
    c = ctx_for(ws)
    r = dispatch("edit_file", {"path": "a.txt", "old_string": "hello", "new_string": "howdy"}, c)
    assert r.ok and (c.workdir / "a.txt").read_text() == "howdy\nworld\n"


def test_edit_file_not_found(ws):
    r = dispatch("edit_file", {"path": "a.txt", "old_string": "nope", "new_string": "x"}, ctx_for(ws))
    assert not r.ok and "not found" in r.output


def test_edit_file_ambiguous_rejected(ws):
    (ctx_for(ws).workdir / "amb.txt").write_text("x\nx\nx\n")
    r = dispatch("edit_file", {"path": "amb.txt", "old_string": "x", "new_string": "y"}, ctx_for(ws))
    assert not r.ok and ("matches 3" in r.output or "ambiguous" in r.output)
    # replace_all fixes it
    r = dispatch("edit_file", {"path": "amb.txt", "old_string": "x", "new_string": "y", "replace_all": True}, ctx_for(ws))
    assert r.ok and r.output.startswith("replaced 3")


# ---------------------------------------------------------------- list_dir / glob

def test_list_dir(ws):
    r = dispatch("list_dir", {"path": "."}, ctx_for(ws))
    assert r.ok and "dir sub" in r.output and "file a.txt" in r.output


def test_glob(ws):
    r = dispatch("glob", {"pattern": "*.txt"}, ctx_for(ws))
    assert r.ok and "a.txt" in r.output and "b.txt" in r.output


# ---------------------------------------------------------------- search

def test_search(ws):
    r = dispatch("search", {"pattern": "world"}, ctx_for(ws))
    # `rg` emits absolute paths; the python fallback emits names. Assert on the
    # line marker shared by both formats, and that the hello line is absent.
    assert r.ok and "hello" not in r.output
    assert "world" in r.output and ":2:" in r.output


def test_search_no_match(ws):
    r = dispatch("search", {"pattern": "zzzz"}, ctx_for(ws))
    assert r.ok and r.output == "(no matches)"


# ---------------------------------------------------------------- update_plan

def test_update_plan_append_replace_clear(ws):
    c = ctx_for(ws)
    r = dispatch("update_plan", {"content": "task one"}, c)
    assert r.ok and "task one" in r.output
    r = dispatch("update_plan", {"content": "task two", "status": "in_progress"}, c)
    assert r.ok and "in_progress" in r.output
    r = dispatch("update_plan", {"mode": "clear"}, c)
    assert r.ok and "(empty plan)" in r.output


# ---------------------------------------------------------------- shell

def test_shell_happy_and_exit_code(ws):
    c = ctx_for(ws, sandbox="danger-full-access")
    r = dispatch("shell", {"command": "echo hi"}, c)
    assert r.ok and "hi" in r.output
    r = dispatch("shell", {"command": "exit 3"}, c)
    assert not r.ok and "exit 3" in r.output


def test_shell_denied_workspace_write(ws):
    c = ctx_for(ws)  # workspace-write
    r = dispatch("shell", {"command": "echo hi"}, c)
    assert not r.ok and "sandbox" in r.output


def test_shell_timeout(ws):
    c = ctx_for(ws, sandbox="danger-full-access", timeout=1)
    import time as _t
    t0 = _t.monotonic()
    r = dispatch("shell", {"command": "sleep 5"}, c)
    assert not r.ok and "timed out" in r.output
    assert _t.monotonic() - t0 < 4


# ---------------------------------------------------------------- web_fetch

def test_web_fetch_http_error_is_soft_failure(ws, monkeypatch):
    from codemonkey.tools import web_fetch

    class _Resp:
        status_code = 404

        def iter_bytes(self):
            yield b"not here"

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class _Client:
        def __init__(self, *a, **k):
            pass

        def stream(self, method, url):
            return _Resp()

        def close(self):
            pass

    monkeypatch.setattr(web_fetch.httpx, "Client", _Client)
    r = web_fetch.run({"url": "https://example.invalid/x"}, ctx_for(ws))
    assert not r.ok and "404" in r.output


# ---------------------------------------------------------------- sandbox policy

def test_sandbox_can_matrix():
    assert can("read_file", "read-only")
    assert not can("write_file", "read-only")
    assert not can("shell", "read-only")
    assert can("write_file", "workspace-write")
    assert not can("shell", "workspace-write")
    assert can("write_file", "danger-full-access")
    assert can("shell", "danger-full-access")
    with pytest.raises(SandboxError):
        can("read_file", "bogus")


def test_validate_root_escape_rejected(ws):
    c = ctx_for(ws)
    with pytest.raises(SandboxError):
        validate_root(c, "../outside.txt")
    with pytest.raises(SandboxError):
        validate_root(c, "/etc/hostname")


def test_add_dir_root(ws, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "o.txt").write_text("o")
    c = ctx_for(ws, add_dirs=[str(other)])
    r = dispatch("read_file", {"path": str(other / "o.txt")}, c)
    assert r.ok and r.output.startswith("     1| o")
    # write works in the added dir
    r = dispatch("write_file", {"path": str(other / "w.txt"), "content": "z"}, c)
    assert r.ok


def test_truncation_marker(ws):
    c = ctx_for(ws)
    (c.workdir / "huge.txt").write_text("z" * (MAX_OUTPUT + 100))
    r = dispatch("read_file", {"path": "huge.txt", "limit": MAX_OUTPUT + 200}, c)
    assert len(r.output) <= MAX_OUTPUT + 200 and "truncated" in r.output


def test_unknown_tool_is_soft_error(ws):
    r = dispatch("bogus_tool", {}, ctx_for(ws))
    assert not r.ok and "unknown tool" in r.output


def test_registry_has_all_nine():
    assert set(names()) == {
        "read_file", "write_file", "edit_file", "list_dir",
        "glob", "search", "shell", "update_plan", "web_fetch",
    }
