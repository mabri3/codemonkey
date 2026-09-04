"""R23B: diff-preview approval mode."""

from __future__ import annotations

import pytest

from codemonkey.diffpreview import (preview_diff_edit, preview_diff_write,
                                    unified_diff)


def test_unified_diff_format():
    d = unified_diff("x.py", "a\nb\n", "a\nc\n")
    assert "--- a/x.py" in d and "+++ b/x.py" in d
    assert "-b" in d and "+c" in d


def test_write_preview_new_file(tmp_path):
    d = preview_diff_write("new.txt", "hello", tmp_path)
    # a new file renders an add-only unified diff (or the explicit marker)
    assert d == "(new file)" or ("+++ b/new.txt" in d and "+hello" in d)


def test_write_preview_existing(tmp_path):
    (tmp_path / "f.txt").write_text("old line\n")
    d = preview_diff_write("f.txt", "new line\n", tmp_path)
    assert "-old line" in d and "+new line" in d


def test_edit_preview_no_change(tmp_path):
    (tmp_path / "f.txt").write_text("keep\n")
    d = preview_diff_edit("f.txt", "ABSENT", "x", tmp_path)
    assert d == "(no change: search text not found)"


def test_edit_preview_roundtrip(tmp_path):
    (tmp_path / "f.txt").write_text("alpha\nbeta\n")
    d = preview_diff_edit("f.txt", "alpha", "ALPHA", tmp_path)
    assert "-alpha" in d and "+ALPHA" in d
