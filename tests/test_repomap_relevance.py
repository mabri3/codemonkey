"""Cycle 27 (loop5): repo-map relevance ranking.

Verify probe (plan.md): >=4 tests — relevance overrides recency for matching
symbols; non-matching fallback keeps cycle-21 order; budget still enforced;
injection stays deterministic across two calls.
"""

from __future__ import annotations

from pathlib import Path

from codemonkey.repomap import rank_files, rank_files_relevant, relevance_score


def _repo(tmp_path: Path) -> None:
    """Git repo where stale.py is the MOST RECENT commit but has low symbol
    density; relevant.py was committed earlier but matches the query."""
    import subprocess

    def git(*args):
        subprocess.run(["git"] + list(args), cwd=tmp_path,
                       capture_output=True, text=True, check=True)

    git("init", "-q")
    git("config", "user.name", "t")
    git("config", "user.email", "t@t")
    # relevant.py committed FIRST (older)
    (tmp_path / "relevant.py").write_text(
        "".join(f"def parser_tool_{i}():\n    pass\n" for i in range(6))
    )
    git("add", "-A")
    git("commit", "-qm", "relevant")
    # stale.py committed LAST (most recent touch)
    (tmp_path / "stale.py").write_text(
        "def alpha_one():\n    pass\n\ndef alpha_two():\n    pass\n"
    )
    git("add", "-A")
    git("commit", "-qm", "stale")


def test_relevance_overrides_recency(tmp_path):
    _repo(tmp_path)
    rmap = {"stale.py": [{"symbol": "alpha_one", "kind": "function", "line": 1},
                          {"symbol": "alpha_two", "kind": "function", "line": 3}],
            "relevant.py": [{"symbol": f"parser_tool_{i}", "kind": "function", "line": i * 2 + 1}
                             for i in range(6)]}
    base = rank_files(rmap, tmp_path)  # cycle-21 order (recency/density)
    assert base.index("stale.py") < base.index("relevant.py")  # stale first by recency

    relevant = rank_files_relevant(rmap, tmp_path, query_terms=["parser_tool"])
    assert relevant.index("relevant.py") < relevant.index("stale.py")


def test_non_matching_keeps_cycle21_order(tmp_path):
    _repo(tmp_path)
    rmap = {"stale.py": [{"symbol": "alpha_one", "kind": "function", "line": 1}],
            "relevant.py": [{"symbol": "parser_tool_0", "kind": "function", "line": 1}]}
    # query terms match NOTHING
    out = rank_files_relevant(rmap, tmp_path, query_terms=["nonexistent_thing"])
    assert out == rank_files(rmap, tmp_path)


def test_score_counts_path_and_symbols():
    entry = [{"symbol": "parse_tool_calls", "kind": "function", "line": 1}]
    assert relevance_score("src/protocol.py", entry, ["protocol"]) > 0
    assert relevance_score("src/protocol.py", entry, ["parse_tool_calls"]) > 0
    assert relevance_score("src/unrelated.py", entry, ["zzz"]) == 0
    assert relevance_score("src/protocol.py", entry, []) == 0  # no terms -> 0


def test_budget_still_enforced_with_relevance(tmp_path):
    big = {"f{i}.py".format(i=i): [{"symbol": f"fn_{i}_{j}", "kind": "function",
                                     "line": j + 1} for j in range(20)]
           for i in range(30)}
    text = rank_files_relevant(big, tmp_path, query_terms=["fn_5"])
    from codemonkey.repomap import render_injection
    inj = render_injection(big, tmp_path, budget=600, query_terms=["fn_5"])
    assert len(inj) <= 600
    # matched file ranked ahead
    lines = inj.splitlines()
    fn5 = next((ln for ln in lines if ln.startswith("f5.py:")), None)
    other = next((ln for ln in lines if ln.startswith("f0.py:")), None)
    if fn5 and other:
        assert lines.index(fn5) < lines.index(other)


def test_injection_deterministic_across_calls(tmp_path):
    from codemonkey.repomap import render_injection

    (tmp_path / "a.py").write_text("def parse_tool_x():\n    pass\n" * 4)
    (tmp_path / "b.py").write_text("def unrelated():\n    pass\n")
    terms = ["parse_tool_x"]
    t1 = render_injection({"a.py": [{"symbol": "parse_tool_x", "kind": "function", "line": 1}],
                           "b.py": [{"symbol": "unrelated", "kind": "function", "line": 1}]},
                          tmp_path, budget=4000, query_terms=terms)
    t2 = render_injection({"a.py": [{"symbol": "parse_tool_x", "kind": "function", "line": 1}],
                           "b.py": [{"symbol": "unrelated", "kind": "function", "line": 1}]},
                          tmp_path, budget=4000, query_terms=terms)
    assert t1 == t2 and t1 != ""
    assert t1.splitlines()[1].startswith("a.py:")  # relevant file first after header
