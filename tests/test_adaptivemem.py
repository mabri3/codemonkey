"""R35: adaptive memory management."""

from __future__ import annotations

import time

from codemonkey.adaptivemem import adaptive_select, score_lines


def test_score_with_recency():
    import datetime as _dt

    old = "stale fact [2020-01-01]"
    fresh = "fresh fact [2026-09-03]"
    timeless = "always true"
    now = _dt.datetime(2026, 9, 3).timestamp()
    scored = dict((l, w) for w, l in score_lines([old, fresh, timeless], now=now))
    assert scored[fresh] > scored[old]
    assert scored[timeless] == 1.0


def test_select_under_budget():
    lines = [f"line {i} " + "word " * 40 for i in range(10)]
    text, dropped = adaptive_select(lines, token_budget=100)
    assert text  # something kept
    assert len(dropped) >= len(lines) - 3  # most dropped under tiny budget


def test_select_prefers_high_score():
    old = "stale [2020-01-01]"
    fresh = "fresh [2026-09-03]"
    now = time.mktime(time.strptime("2026-09-03", "%Y-%m-%d"))
    text, dropped = adaptive_select([old, fresh], token_budget=3, now=now)
    assert fresh in text and old in dropped


def test_original_order_preserved():
    a = "alpha note"
    b = "beta note"
    text, dropped = adaptive_select([a, b], token_budget=100)
    assert text == "alpha note\nbeta note"


def test_empty_memory():
    text, dropped = adaptive_select([], token_budget=100)
    assert text == "" and dropped == []
