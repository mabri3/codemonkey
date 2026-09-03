"""Cycle 29 (loop6): KV-cache telemetry.

Verify probe (plan.md): >=5 tests — timings parse (non-streaming + streaming),
ratio math, absent-timings tolerance, summary line, eval field.
"""

from __future__ import annotations

import json

import pytest

from codemonkey.cost import cache_ratio, render_summary, summarize


# ---------------- timings -> usage surface (provider) ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {}
        self.tool_calls = []


def test_nonstreaming_timings_surface_cached_tokens(monkeypatch):
    from codemonkey.providers.openai import OpenAIProvider

    p = OpenAIProvider.__new__(OpenAIProvider)
    p.base_url = "http://x/v1"
    p.model = "m"
    p.api_key = "k"
    p.max_retries = 0

    def fake_request(path, body):
        return {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 100, "prompt_tokens": 80, "completion_tokens": 20},
            "timings": {"cache_n": 60, "prompt_n": 80},
        }

    p._request = fake_request
    turn = p.chat([{"role": "user", "content": "hi"}])
    assert turn.usage["cached_tokens"] == 60


def test_nonstreaming_without_timings_no_field(monkeypatch):
    from codemonkey.providers.openai import OpenAIProvider

    p = OpenAIProvider.__new__(OpenAIProvider)
    p.base_url = "http://x/v1"
    p.model = "m"
    p.api_key = "k"
    p.max_retries = 0

    def fake_request(path, body):
        return {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 5}}

    p._request = fake_request
    turn = p.chat([{"role": "user", "content": "hi"}])
    assert "cached_tokens" not in turn.usage


# ---------------- summarize + ratio + render ----------------

def test_summarize_includes_cached():
    events = [
        {"type": "turn.completed", "usage": {"total_tokens": 100,
         "prompt_tokens": 80, "completion_tokens": 20, "cached_tokens": 60}},
    ]
    s = summarize(events)
    assert s["cached_tokens"] == 60
    assert cache_ratio(s) == 0.75


def test_cache_ratio_edge_cases():
    assert cache_ratio({"prompt_tokens": 0, "cached_tokens": 0}) is None
    assert cache_ratio({"prompt_tokens": 0, "cached_tokens": 10}) is None
    s = {"prompt_tokens": 10, "cached_tokens": 99}  # clamp >1.0
    assert cache_ratio(s) == 1.0


def test_render_summary_cache_line():
    s = {"turns": 2, "total_tokens": 100, "prompt_tokens": 80,
         "completion_tokens": 20, "cached_tokens": 60, "tool_calls": {},
         "wall_seconds": 1.0}
    text = render_summary(s)
    assert "cache: 60/80 tokens (75%)" in text


def test_render_summary_no_cache_signal():
    s = {"turns": 1, "total_tokens": 5, "prompt_tokens": 0,
         "completion_tokens": 5, "tool_calls": {}, "wall_seconds": 0.5}
    assert "cache:" not in render_summary(s)


def test_exec_cost_summary_shows_cache(monkeypatch):
    """--cost-summary surfaces a cache line when the server reports timings."""
    import subprocess

    repo = "/Users/bharris/Programs/CodeMonkey"
    monkeypatch.chdir(repo)
    r = subprocess.run(
        ["uv", "run", "codemonkey", "exec", "--ephemeral", "--cost-summary",
         "Reply with exactly: cache-probe"],
        capture_output=True, text=True, timeout=420, cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # home server returns timings; cache line must appear (ratio may be 0%)
    assert "cache:" in r.stderr
