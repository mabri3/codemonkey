"""Cycle 34 (loop8): batched multi-file SREP edits."""

from __future__ import annotations

import pytest

from codemonkey.sandbox import ToolContext
from codemonkey.tools.edit_file import run


@pytest.fixture()
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


def _seed(tmp_path):
    (tmp_path / "a.py").write_text("def old_a():\n    return 1\n")
    (tmp_path / "b.py").write_text("def old_b():\n    return 2\n")


SREP_A = """<<<< SEARCH
def old_a():
>>>> REPLACE
def new_a():
"""

SREP_B = """<<<< SEARCH
def old_b():
>>>> REPLACE
def new_b():
"""


def test_multi_file_apply(tmp_path, ctx):
    _seed(tmp_path)
    res = run({"edits": [
        {"path": "a.py", "search": "old_a", "replace": "new_a"},
        {"path": "b.py", "patch": SREP_B},
    ]}, ctx)
    assert res.ok, res.output
    assert (tmp_path / "a.py").read_text() == "def new_a():\n    return 1\n"
    assert (tmp_path / "b.py").read_text() == "def new_b():\n    return 2\n"


def test_atomic_no_partial_apply(tmp_path, ctx):
    _seed(tmp_path)
    # second edit fails (search missing) -> first must NOT be written
    res = run({"edits": [
        {"path": "a.py", "search": "old_a", "replace": "new_a"},
        {"path": "b.py", "search": "does-not-exist", "replace": "x"},
    ]}, ctx)
    assert not res.ok
    assert (tmp_path / "a.py").read_text() == "def old_a():\n    return 1\n"
    assert (tmp_path / "b.py").read_text() == "def old_b():\n    return 2\n"


def test_single_file_back_compat(tmp_path, ctx):
    _seed(tmp_path)
    res = run({"path": "a.py", "old_string": "old_a", "new_string": "new_a"}, ctx)
    assert res.ok
    assert (tmp_path / "a.py").read_text() == "def new_a():\n    return 1\n"


def test_per_file_outcomes_listed(tmp_path, ctx):
    _seed(tmp_path)
    res = run({"edits": [
        {"path": "a.py", "search": "old_a", "replace": "new_a"},
        {"path": "b.py", "search": "old_b", "replace": "new_b"},
    ]}, ctx)
    assert res.ok
    assert "a.py: applied" in res.output
    assert "b.py: applied" in res.output


def test_error_names_failing_edit(tmp_path, ctx):
    _seed(tmp_path)
    res = run({"edits": [
        {"path": "a.py", "search": "old_a", "replace": "new_a"},
        {"path": "missing.py", "search": "x", "replace": "y"},
    ]}, ctx)
    assert not res.ok
    assert "edit 2" in res.output and "missing.py" in res.output


def test_journal_records_per_file(tmp_path, ctx, monkeypatch):
    import tempfile

    home = tempfile.mkdtemp()
    monkeypatch.setenv("HOME", home)
    _seed(tmp_path)
    from codemonkey.loop import run_turns

    class Turn:
        def __init__(self, c):
            self.content = c
            self.usage = {"total_tokens": 1}
            self.tool_calls = []

    class Prov:
        n = 0

        def chat(self, messages, **kw):
            Prov.n += 1
            if Prov.n == 1:
                return Turn(json_batch_call())
            return Turn("done")

    def json_batch_call():
        import json as _j
        return "TOOL_CALL: " + _j.dumps({
            "name": "edit_file",
            "arguments": {"edits": [
                {"path": "a.py", "search": "old_a", "replace": "new_a"},
                {"path": "b.py", "search": "old_b", "replace": "new_b"},
            ]}}) + "\n"

    run_turns(Prov(), "go", ctx, tool_protocol="prompt", max_turns=3,
              journal_thread="t-batch")
    from codemonkey.journal import read_thread

    recs = [r for r in read_thread("t-batch") if r["tool"] == "edit_file"]
    assert recs, "edit_file journaled"


# -- CYCLE 34F1 (critic-loop8 finding 3) ---------------------------------
# Two edits on the SAME file used to be planned from separate disk reads, so
# the second write clobbered the first while the result still said "applied".

def _ctx(tmp_path):
    from codemonkey.sandbox import ToolContext

    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


def test_two_edits_on_one_file_both_land(tmp_path):
    from codemonkey.tools import dispatch

    f = tmp_path / "a.txt"
    f.write_text("alpha\nbeta\n")
    r = dispatch("edit_file", {"edits": [
        {"path": "a.txt", "search": "alpha", "replace": "ALPHA"},
        {"path": "a.txt", "search": "beta", "replace": "BETA"},
    ]}, _ctx(tmp_path))
    assert r.ok, r.output
    assert f.read_text() == "ALPHA\nBETA\n"


def test_same_file_listed_once_in_the_outcome(tmp_path):
    from codemonkey.tools import dispatch

    (tmp_path / "a.txt").write_text("alpha\nbeta\n")
    r = dispatch("edit_file", {"edits": [
        {"path": "a.txt", "search": "alpha", "replace": "ALPHA"},
        {"path": "./a.txt", "search": "beta", "replace": "BETA"},
    ]}, _ctx(tmp_path))
    assert r.ok, r.output
    assert r.output.count("applied") == 2  # header + one per-file line
    assert "1 file(s)" in r.output


def test_second_edit_on_same_file_failing_writes_nothing(tmp_path):
    from codemonkey.tools import dispatch

    f = tmp_path / "a.txt"
    f.write_text("alpha\nbeta\n")
    r = dispatch("edit_file", {"edits": [
        {"path": "a.txt", "search": "alpha", "replace": "ALPHA"},
        {"path": "a.txt", "search": "nowhere", "replace": "X"},
    ]}, _ctx(tmp_path))
    assert not r.ok
    assert f.read_text() == "alpha\nbeta\n"  # atomic: nothing written


def test_later_edit_sees_the_earlier_edit_text(tmp_path):
    """An edit may target text produced by a previous edit in the same batch."""
    from codemonkey.tools import dispatch

    f = tmp_path / "a.txt"
    f.write_text("one\n")
    r = dispatch("edit_file", {"edits": [
        {"path": "a.txt", "search": "one", "replace": "two"},
        {"path": "a.txt", "search": "two", "replace": "three"},
    ]}, _ctx(tmp_path))
    assert r.ok, r.output
    assert f.read_text() == "three\n"
