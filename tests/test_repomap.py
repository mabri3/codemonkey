"""Cycle 20 (loop4): repo map — def-scan, cache, repo_map tool.

Verify probe (plan.md): >=6 tests — py/js/go fixture extraction with correct
1-based lines; cache hit (scanner not re-entered); touch invalidates only that
entry; ignore list honored; deterministic limit truncation; binary skip.
"""

from __future__ import annotations

import pytest

from codemonkey import repomap as rm
from codemonkey.tools import dispatch


class Ctx:
    def __init__(self, tmp_path):
        from codemonkey.sandbox import ToolContext

        self.tc = ToolContext(workdir=tmp_path, sandbox="read-only", timeout=10)
        self.workdir = self.tc.workdir

    def __getattr__(self, name):
        return getattr(self.tc, name)


PY = "def top_fn():\n    pass\n\nclass TopClass:\n    def method(self):\n        pass\n"
JS = "function jsFn() {}\nconst arrow = (a) => a;\nclass JsClass {}\n"
GO = "package main\n\nfunc main() {}\nfunc helper(x int) int { return x }\ntype T struct {}\n"


def test_python_def_class_lines(tmp_path):
    f = tmp_path / "m.py"
    f.write_text(PY)
    entries = rm.scan_file(f)
    got = {(e["symbol"], e["kind"]): e["line"] for e in entries}
    assert got[("top_fn", "def")] == 1
    assert got[("TopClass", "class")] == 4
    assert got[("method", "def")] == 5  # indented methods count, 1-based


def test_js_and_go_fixtures(tmp_path):
    (tmp_path / "a.js").write_text(JS)
    (tmp_path / "main.go").write_text(GO)
    m = rm.scan_repo(tmp_path, use_cache=False)
    js = {(e["symbol"], e["kind"]) for e in m["a.js"]}
    assert ("jsFn", "function") in js and ("arrow", "function") in js
    go = {(e["symbol"], e["kind"]) for e in m["main.go"]}
    assert ("main", "func") in go and ("T", "struct") in go


def test_cache_hit_no_rescan(tmp_path, monkeypatch):
    f = tmp_path / "m.py"
    f.write_text(PY)
    rm.scan_repo(tmp_path)  # populate cache
    calls = {"n": 0}
    orig = rm.scan_file
    def spy(path):
        calls["n"] += 1
        return orig(path)
    monkeypatch.setattr(rm, "scan_file", spy)
    m = rm.scan_repo(tmp_path)  # unchanged mtime+size -> cache hit
    assert calls["n"] == 0
    assert "m.py" in m


def test_touch_invalidates_only_that_file(tmp_path, monkeypatch):
    import os
    (tmp_path / "a.py").write_text("def a():\n    pass\n")
    (tmp_path / "b.py").write_text("def b():\n    pass\n")
    rm.scan_repo(tmp_path)
    hits = []
    # change only b.py
    with open(tmp_path / "b.py", "a") as f:
        f.write("def b2():\n    pass\n")
    os.utime(tmp_path / "a.py", (1000000, 1000000))  # a unchanged content? mtime changed!
    # force a's cache entry to look unchanged: rewrite stat via cache key check
    # simpler: only b should be rescanned -> spy counts
    calls = {"n": 0}
    orig = rm.scan_file
    def spy(path):
        calls["n"] += 1
        return orig(path)
    monkeypatch.setattr(rm, "scan_file", spy)
    # restore a.py mtime to its cached value via the cache file
    cache = rm._load_cache(tmp_path)
    import os as _os
    st = _os.stat(tmp_path / "a.py")
    # a's cached mtime was overwritten by utime — set cache to match current stat
    cache["a.py"]["mtime"] = st.st_mtime
    rm._save_cache(tmp_path, cache)
    m = rm.scan_repo(tmp_path)
    scanned = [str(p) for p in [None]] if False else None
    assert calls["n"] == 1  # only b.py re-scanned


def test_ignore_dirs_honored(tmp_path):
    junk = tmp_path / "node_modules"
    junk.mkdir()
    (junk / "x.js").write_text(JS)
    (tmp_path / "keep.js").write_text(JS)
    m = rm.scan_repo(tmp_path, use_cache=False)
    assert "keep.js" in m
    assert not any(k.startswith("node_modules") for k in m)


def test_limit_truncates_deterministically(tmp_path):
    f = tmp_path / "big.py"
    f.write_text("".join(f"def fn_{i:03d}():\n    pass\n" for i in range(50)))
    m = rm.scan_repo(tmp_path, use_cache=False)
    out = rm.format_map(m, limit=10)
    assert out.count("fn_") == 10
    assert "truncated" in out
    # deterministic: same output twice
    assert out == rm.format_map(m, limit=10)


def test_binary_file_skipped_not_fatal(tmp_path):
    (tmp_path / "bin.py").write_bytes(b"\x00\x01\x02\xff\xfe")
    (tmp_path / "ok.py").write_text("def fine():\n    pass\n")
    m = rm.scan_repo(tmp_path, use_cache=False)
    assert "ok.py" in m
    assert "bin.py" not in m  # skipped silently


# ---------------- tool surface ----------------

def test_repo_map_tool_dispatch(tmp_path):
    (tmp_path / "mod.py").write_text("def parser_fn():\n    pass\n")
    r = dispatch("repo_map", {"path": "."}, Ctx(tmp_path))
    assert r.ok
    assert "mod.py" in r.output and "parser_fn" in r.output


def test_repo_map_tool_pattern_filter(tmp_path):
    (tmp_path / "keepme.py").write_text("def alpha():\n    pass\n")
    (tmp_path / "dropme.py").write_text("def beta():\n    pass\n")
    r = dispatch("repo_map", {"path": ".", "pattern": "keep*"}, Ctx(tmp_path))
    assert r.ok
    assert "keepme.py" in r.output and "dropme.py" not in r.output
