"""Loop 20 (cycle 57): tool-arg validation gate."""

from __future__ import annotations

import pytest

from codemonkey.argvalidate import validate_args


def test_missing_required_names_field():
    bad = validate_args("write_file", {"path": "x.txt"})
    assert bad["error_class"] == "schema_mismatch"
    assert "content" in bad["detail"]


def test_wrong_type_detected():
    bad = validate_args("shell", {"command": 123})
    assert bad is not None
    assert "'command' must be str" in bad["detail"]


def test_valid_pass_through():
    assert validate_args("shell", {"command": "ls"}) is None
    assert validate_args("write_file", {"path": "a", "content": "b"}) is None
    assert validate_args("list_dir", {}) is None


def test_strict_unknown_keys():
    assert validate_args("shell", {"command": "x", "junk": 1}, strict=True) is not None
    assert validate_args("shell", {"command": "x", "junk": 1}) is None  # default lenient


def test_non_dict_args():
    bad = validate_args("shell", "rm -rf")
    assert bad["error_class"] == "schema_mismatch"


def test_unknown_tool_pass_through():
    assert validate_args("future_tool", {"anything": 1}) is None


def test_classification_roundtrip(tmp_path, monkeypatch):
    """The journal contract the loop uses: status=error +
    error_class=schema_mismatch persists with the field detail."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from codemonkey.journal import read_thread, record

    bad = validate_args("shell", {})
    assert bad is not None
    record("t57", "outcome", tool="shell", key="k", status="error",
           error_class="schema_mismatch", output=bad["detail"])
    recs = read_thread("t57")
    assert any(r.get("error_class") == "schema_mismatch" for r in recs)
