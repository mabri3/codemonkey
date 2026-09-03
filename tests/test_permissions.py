"""Cycle 36 (loop9): rule-based permissions."""

from __future__ import annotations

import pytest

from codemonkey.permissions import evaluate


RULES = [
    {"tool": "shell", "pattern": "git status*", "action": "allow"},
    {"tool": "shell", "pattern": "rm -rf*", "action": "deny"},
    {"tool": "write_file", "pattern": "*.env", "action": "deny"},
    {"tool": "web_fetch", "action": "ask"},
]


def test_allow_first_match_wins():
    assert evaluate(RULES, "shell", {"command": "git status --short"}) == "allow"


def test_deny_beats_allow_order():
    # deny tier evaluated before allow even if listed later
    rules = [
        {"tool": "shell", "pattern": "git*", "action": "allow"},
        {"tool": "shell", "pattern": "git push*", "action": "deny"},
    ]
    assert evaluate(rules, "shell", {"command": "git push origin"}) == "deny"
    assert evaluate(rules, "shell", {"command": "git status"}) == "allow"


def test_ask_tier():
    assert evaluate(RULES, "web_fetch", {"url": "http://x"}) == "ask"


def test_no_match_returns_none():
    assert evaluate(RULES, "shell", {"command": "make all"}) is None
    assert evaluate([], "shell", {"command": "anything"}) is None


def test_file_tool_path_pattern():
    assert evaluate(RULES, "write_file", {"path": ".env", "content": "x"}) == "deny"
    assert evaluate(RULES, "write_file", {"path": "src/app.py", "content": "x"}) is None


def test_malformed_rule_raises():
    with pytest.raises(ValueError):
        evaluate([{"tool": "shell"}], "shell", {})  # no action
    with pytest.raises(ValueError):
        evaluate([{"tool": "shell", "action": "maybe"}], "shell", {})


def test_wildcard_tool():
    rules = [{"tool": "*", "pattern": "rm -rf*", "action": "deny"}]
    assert evaluate(rules, "shell", {"command": "rm -rf /"}) == "deny"
    assert evaluate(rules, "shell", {"command": "ls"}) is None


def test_pattern_requires_subject():
    # non-shell/path tools have empty subject -> pattern rules never match
    rules = [{"tool": "update_plan", "pattern": "x*", "action": "deny"}]
    assert evaluate(rules, "update_plan", {"items": []}) is None
