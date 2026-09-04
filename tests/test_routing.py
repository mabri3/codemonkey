"""Cycle 53 (loop17): static model routing."""

from __future__ import annotations

import pytest

from codemonkey.routing import route_stats, select_route, validate_rules


RULES = [
    {"when": {"tool_role": "review"},
     "use": {"provider": "local", "model": "big-moe"}},
    {"when": {"prompt_glob": "*compliance*"},
     "use": {"provider": "local", "model": "alt-model"}},
]


def test_first_match_wins():
    r = select_route(RULES, prompt="review compliance docs", tool_role="review")
    assert r["provider"] == "local"
    assert r["model"] == "big-moe"
    assert r["rule_index"] == 0  # first match, not the glob


def test_prompt_glob_match():
    r = select_route(RULES, prompt="check COMPLIANCE status", tool_role="")
    assert r["model"] == "alt-model"
    assert r["rule_index"] == 1


def test_no_match_falls_back_to_default():
    r = select_route(RULES, prompt="write a poem", tool_role="",
                     default_provider="local", default_model="default-m")
    assert r == {"provider": "local", "model": "default-m", "rule_index": None}


def test_route_recorded_in_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from codemonkey.journal import read_thread, record

    sel = select_route(RULES, prompt="x", tool_role="review")
    record("rt", "outcome", tool="route", key="run1", status="applied",
           output=f"{sel['provider']}/{sel['model']} rule={sel['rule_index']}")
    recs = read_thread("rt")
    assert any(r["tool"] == "route" and "big-" in r["output"] for r in recs)


def test_invalid_rules_rejected():
    assert validate_rules([{"use": {"provider": "x"}}]) is not None
    assert validate_rules([{"when": {}, "use": {}}]) is not None
    assert validate_rules("nope") is not None
    assert validate_rules(RULES) is None


def test_route_stats_aggregation():
    results = {"tasks": [
        {"route_provider": "local", "route_model": "a", "ok": True, "total_tokens": 10},
        {"route_provider": "local", "route_model": "a", "ok": False, "total_tokens": 5},
        {"route_provider": "local", "route_model": "b", "ok": True, "total_tokens": 7},
    ]}
    stats = route_stats(results)
    assert stats["local/a"]["pass_rate"] == 0.5
    assert stats["local/a"]["tokens"] == 15
    assert stats["local/b"]["pass_rate"] == 1.0
