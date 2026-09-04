"""VRAM→tokens budget calculator (loop19, cycle 56).

Per-token KV-cache bytes = 2 (K+V) × layers × kv_heads × head_dim × bytes.
Given a VRAM headroom and model internals (or override flags), compute the
largest SAFE context_limit and split it: observation budget = 40% (defaults),
and emit a copiable config.yaml block. Priority note (BaKlaVa client-analog):
system > memory > recent history > repo-map density.

bytes-per-weight: fp16=2, q8=1, q4=0.5 (approximation for KV quant variants).
"""

from __future__ import annotations

from typing import Optional

# Qwen3.8-27B-class defaults (documented approximations; override via flags)
DEFAULT_LAYERS = 64
DEFAULT_KV_HEADS = 8
DEFAULT_HEAD_DIM = 128
DEFAULT_BYTES = 2  # fp16 KV
DEFAULT_WEIGHTS_GB = 54.0  # 27B at ~q4/q8 mix on the server


def kv_bytes_per_token(layers: int, kv_heads: int, head_dim: int,
                       bytes_per_weight: float = DEFAULT_BYTES) -> int:
    return int(2 * layers * kv_heads * head_dim * bytes_per_weight)


def safe_context_limit(*, vram_headroom_gb: float,
                       layers: int = DEFAULT_LAYERS,
                       kv_heads: int = DEFAULT_KV_HEADS,
                       head_dim: int = DEFAULT_HEAD_DIM,
                       bytes_per_weight: float = DEFAULT_BYTES,
                       weights_gb: float = DEFAULT_WEIGHTS_GB,
                       safety_factor: float = 0.85) -> dict:
    """Largest context whose KV + weights fit under vram_headroom_gb."""
    bpt = kv_bytes_per_token(layers, kv_heads, head_dim, bytes_per_weight)
    usable_gb = max(0.0, vram_headroom_gb - weights_gb) * safety_factor
    max_tokens = int(usable_gb * (1024 ** 3) / max(bpt, 1))
    # round DOWN to a clean 1k boundary
    clean = (max_tokens // 1024) * 1024
    return {
        "kv_bytes_per_token": bpt,
        "usable_gb": round(usable_gb, 2),
        "max_tokens": max(0, clean),
        "observation_budget": int(max(0, clean) * 0.4),
        "internals": {"layers": layers, "kv_heads": kv_heads,
                      "head_dim": head_dim,
                      "bytes_per_weight": bytes_per_weight,
                      "weights_gb": weights_gb},
    }


def render_yaml(rec: dict) -> str:
    return (f"context_limit: {rec['max_tokens']}\n"
            f"observation_budget: {rec['observation_budget']}\n")


def validate_budget(vram_gb: float, layers: Optional[int], kv_heads: Optional[int],
                    head_dim: Optional[int]) -> Optional[str]:
    if vram_gb is None or vram_gb <= 0:
        return "--vram-gb must be a positive number"
    if weights_exceed(vram_gb):
        return ("--vram-gb is below the model weights footprint "
                f"({DEFAULT_WEIGHTS_GB:.0f} GB); the model cannot load")
    if (layers is None) != (kv_heads is None) or (layers is None) != (head_dim is None):
        return "provide --layers, --kv-heads and --head-dim together"
    return None


def weights_exceed(vram_gb: float) -> bool:
    return vram_gb < DEFAULT_WEIGHTS_GB
