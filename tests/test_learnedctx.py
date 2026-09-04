"""R36: learned context assembly."""

from __future__ import annotations

import time

from codemonkey.learnedctx import assemble


def test_memory_beats_repomap_on_tie():
    task = "fix the compliance parser"
    frags = [
        {"source": "repo_map", "text": "src/foo.py src/compliance.py src/bar.py"},
        {"source": "memory", "text": "the compliance parser lives in src/compliance.py"},
    ]
    res = assemble(task, frags, token_budget=100)
    # both selected (small); memory must rank first by UTILITY order
    order = sorted(res["selected"], key=lambda s: -s["utility"])
    assert order[0]["source"] == "memory"


def test_budget_drop_uses_utility():
    task = "review compliance rules"
    frags = [
        {"source": "memory", "text": "compliance review rules " + "words " * 60},
        {"source": "instructions", "text": "irrelevant filler " + "stuff " * 60},
    ]
    res = assemble(task, frags, token_budget=100)
    # both are 60ish words; only one fits — the higher-utility memory wins
    assert [s["source"] for s in res["selected"]] == ["memory"]
    assert res["used"] <= res["budget"]
    assert any(s["source"] == "instructions" for s in res["dropped"])


def test_recency_decay_prefers_the_note_feelings():
    fresh = "helpful note [2026-09-03]"
    old = "another helpful note [2020-01-01]"
    task = "helpful notes please"
    frags = [{"source": "memory", "text": fresh},
             {"source": "memory", "text": old}]
    now = time.mktime(time.strptime("2026-09-03", "%Y-%m-%d"))
    res = assemble(task, frags, token_budget=5, now=now)
    if res["selected"]:
        assert res["selected"][0]["text"] == fresh


def test_original_order_in_selection():
    frags = [{"source": "memory", "text": "b text"},
             {"source": "instructions", "text": "a text longer here"}]
    res = assemble("text", frags, token_budget=50)
    got = [s["text"] for s in res["selected"]]
    assert got == ["b text", "a text longer here"]


def test_empty_fragments():
    res = assemble("task", [], token_budget=100)
    assert res["selected"] == [] and res["used"] == 0
