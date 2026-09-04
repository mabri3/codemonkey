"""Cycle 56 (loop19): codemonkey budget — VRAM→tokens calculator."""

from __future__ import annotations

from codemonkey.budget import (DEFAULT_LAYERS, kv_bytes_per_token,
                               render_yaml, safe_context_limit,
                               validate_budget)


def test_kv_bytes_formula():
    # 2 (K+V) × 64 layers × 8 kv_heads × 128 dim × 2 bytes = 262144
    assert kv_bytes_per_token(64, 8, 128, 2.0) == 2 * 64 * 8 * 128 * 2


def test_safe_limit_rounds_down_to_1k():
    rec = safe_context_limit(vram_headroom_gb=64.0)
    assert rec["max_tokens"] % 1024 == 0
    assert rec["max_tokens"] > 0
    assert rec["observation_budget"] == int(rec["max_tokens"] * 0.4)


def test_yaml_block_render():
    rec = safe_context_limit(vram_headroom_gb=64.0)
    y = render_yaml(rec)
    assert f"context_limit: {rec['max_tokens']}" in y
    assert f"observation_budget: {rec['observation_budget']}" in y


def test_metadata_missing_honest_error():
    # weights alone exceed the headroom
    err = validate_budget(40.0, None, None, None)
    assert err and "cannot load" in err
    # partial internals
    err2 = validate_budget(80.0, 64, None, None)
    assert err2 and "together" in err2
    # happy path
    assert validate_budget(80.0, None, None, None) is None


def test_override_flags_honored():
    rec = safe_context_limit(vram_headroom_gb=80.0, layers=32, kv_heads=8,
                             head_dim=128, bytes_per_weight=1.0)
    assert rec["internals"]["layers"] == 32
    assert rec["kv_bytes_per_token"] == kv_bytes_per_token(32, 8, 128, 1.0)


def test_observation_budget_is_40pct():
    rec = safe_context_limit(vram_headroom_gb=90.0)
    assert rec["observation_budget"] == rec["max_tokens"] * 40 // 100
