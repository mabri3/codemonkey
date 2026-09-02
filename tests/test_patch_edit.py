"""Cycle 13 (loop2): search/replace patch editing (SREP blocks in edit_file).

Verify probe (plan.md): >=6 tests — exact, fuzzy, no-match error with
near-miss anchors, atomicity on failure, multi-block; classic form intact.
"""

from __future__ import annotations

from codemonkey.tools import dispatch
from codemonkey.tools.edit_file import parse_blocks


class Ctx:
    def __init__(self, tmp_path):
        from codemonkey.sandbox import ToolContext

        self.tc = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)
        self.workdir = self.tc.workdir

    def __getattr__(self, name):
        return getattr(self.tc, name)


def _dispatch(tmp_path, args):
    return dispatch("edit_file", args, Ctx(tmp_path))


# ---------------- block parsing ----------------

def test_parse_two_blocks():
    patch = (
        "<<<< SEARCH\n"
        "alpha\n"
        ">>>> REPLACE\n"
        "beta\n"
        "<<<< SEARCH\n"
        "gamma\n"
        ">>>> REPLACE ALL\n"
        "delta\n"
    )
    blocks = parse_blocks(patch)
    assert len(blocks) == 2
    assert blocks[0] == {"old": "alpha", "new": "beta", "replace_all": False}
    assert blocks[1]["replace_all"] is True


# ---------------- patch editing semantics ----------------

def test_patch_exact_match(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("def one():\n    return 1\n\ndef two():\n    return 2\n")
    r = _dispatch(tmp_path, {
        "path": "a.py",
        "patch": "<<<< SEARCH\ndef two():\n    return 2\n>>>> REPLACE\ndef two():\n    return 22\n",
    })
    assert r.ok, r.output
    assert "return 22" in f.read_text()
    assert "return 1" in f.read_text()


def test_patch_fuzzy_whitespace_tolerant(tmp_path):
    f = tmp_path / "b.py"
    f.write_text("class Foo:\n      def bar(self):\n            pass\n")
    # model writes different indentation than the file
    r = _dispatch(tmp_path, {
        "path": "b.py",
        "patch": "<<<< SEARCH\nclass Foo:\n  def bar(self):\n    pass\n>>>> REPLACE\nclass Foo:\n  def bar(self):\n    return 7\n",
    })
    assert r.ok, r.output
    assert "fuzzy" in r.output
    assert "return 7" in f.read_text()


def test_patch_no_match_lists_near_miss_anchors(tmp_path):
    f = tmp_path / "c.py"
    f.write_text("def target_fn():\n    return 'real'\n\nother = 1\n")
    r = _dispatch(tmp_path, {
        "path": "c.py",
        "patch": (
            "<<<< SEARCH\ndef target_fn():\n    return 'typo'\n>>>> REPLACE\nnothing\n"
            "<<<< SEARCH\nother = 1\n>>>> REPLACE\nother = 2\n"
        ),
    })
    assert not r.ok
    assert "block 1/2" in r.output
    assert "NOT modified" in r.output        # atomicity message
    assert "target_fn" in r.output            # near-miss anchor named
    # atomic: second block must NOT have been applied
    assert "other = 1" in f.read_text()


def test_patch_multi_block_all_or_nothing(tmp_path):
    f = tmp_path / "multi.txt"
    f.write_text("one\ntwo\nthree\n")
    r = _dispatch(tmp_path, {
        "path": "multi.txt",
        "patch": (
            "<<<< SEARCH\none\n>>>> REPLACE\nONE\n"
            "<<<< SEARCH\ntwo\n>>>> REPLACE\nTWO\n"
            "<<<< SEARCH\n FOUR \n>>>> REPLACE\nFOUR\n"   # doesn't exist anywhere
        ),
    })
    assert not r.ok and "block 3/3" in r.output
    # bytes untouched (no torn intermediate)
    assert f.read_text() == "one\ntwo\nthree\n"


def test_patch_ambiguous_requires_replace_all(tmp_path):
    f = tmp_path / "dup.txt"
    f.write_text("dup\ndup\nend\n")
    r = _dispatch(tmp_path, {
        "path": "dup.txt",
        "patch": "<<<< SEARCH\ndup\n>>>> REPLACE\nunique\n",
    })
    assert not r.ok and "2 places" in r.output
    r2 = _dispatch(tmp_path, {
        "path": "dup.txt",
        "patch": "<<<< SEARCH\ndup\n>>>> REPLACE ALL\nunique\n",
    })
    assert r2.ok
    assert f.read_text() == "unique\nunique\nend\n"


def test_classic_form_still_works(tmp_path):
    f = tmp_path / "classic.txt"
    f.write_text("hello world\n")
    r = _dispatch(tmp_path, {"path": "classic.txt", "old_string": "world", "new_string": "there"})
    assert r.ok and "replaced 1 occurrence" in r.output
    assert f.read_text() == "hello there\n"


def test_classic_fuzzy_fallback(tmp_path):
    f = tmp_path / "fuzzy.txt"
    f.write_text("def  spaced():\n      return 'x'\n")
    # different spacing on both lines
    r = _dispatch(tmp_path, {"path": "fuzzy.txt", "old_string": "def spaced():\n  return 'x'", "new_string": "def spaced():\n    return 'y'"})
    assert r.ok and "fuzzy" in r.output
    assert "return 'y'" in f.read_text()
