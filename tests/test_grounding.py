"""R29: pre-apply validation + symbol index."""

from __future__ import annotations

from codemonkey.grounding import (locate, pre_apply_validate, symbol_index)


def test_python_syntax_caught():
    err = pre_apply_validate("x.py", "def broken(:\n")
    assert err and "syntax error" in err and "line 1" in err


def test_python_valid_passes():
    assert pre_apply_validate("x.py", "def ok():\n    return 1\n") is None


def test_json_validation():
    assert pre_apply_validate("x.json", '{"a": 1}') is None
    err = pre_apply_validate("x.json", "{bad}")
    assert err and "JSON" in err


def test_other_extensions_unvalidated():
    assert pre_apply_validate("x.txt", "anything ( at all") is None


def test_symbol_index_defines(tmp_path):
    (tmp_path / "m.py").write_text("def run_exec(x):\n    return x\n\n\nclass Runa:\n    pass\n")
    idx = symbol_index(tmp_path)
    assert idx["run_exec"] == ["m.py:1"]
    assert idx["Runa"] == ["m.py:5"]


def test_locate_exact_and_prefix(tmp_path):
    idx = {"run_exec": ["a.py:1"], "run_exec_2": ["b.py:9"]}
    assert locate(idx, "run_exec") == ["a.py:1"]
    hits = locate(idx, "run_ex")
    assert set(hits) == {"a.py:1", "b.py:9"}
    assert locate(idx, "nope") == []
