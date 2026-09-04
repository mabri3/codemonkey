"""Loop 22 (cycle 59): exec --dry-run preview mode."""

from __future__ import annotations

import pytest

from codemonkey.dryrun import MUTATING, preview_for


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []
        self.reasoning = ""


def test_write_preview():
    p = preview_for("write_file", {"path": "x.txt", "content": "hello world"})
    assert p.startswith("DRY-RUN (not executed): write_file x.txt")
    assert "11 bytes" in p


def test_edit_preview():
    p = preview_for("edit_file", {"path": "a", "old_string": "12345",
                                  "new_string": "12"})
    assert "search 5 chars -> replace 2 chars" in p


def test_shell_preview():
    p = preview_for("shell", {"command": "echo hi"})
    assert "shell $ echo hi" in p


def test_read_tools_not_mutating():
    assert "read_file" not in MUTATING
    assert "glob" not in MUTATING
    assert "write_file" in MUTATING and "shell" in MUTATING


def test_journal_preview_record(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from codemonkey.journal import read_thread, record

    # the loop writes type=preview records; simulate the contract
    record("tp", "preview", tool="shell", key="k", status="preview",
           output="DRY-RUN (not executed): shell $ echo hi")
    recs = read_thread("tp")
    assert any(r.get("type") == "preview" for r in recs)
