"""Env quarantine for env-sensitive tests (loop23, cycle 60)."""

from __future__ import annotations

import os
from typing import Optional

CODEMONKEY_VARS_PREFIX = "CODEMONKEY_"


def snapshot_codemonkey_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items()
            if k.startswith(CODEMONKEY_VARS_PREFIX)}


def restore_codemonkey_env(snap: dict[str, str]) -> None:
    for k in [k for k in os.environ if k.startswith(CODEMONKEY_VARS_PREFIX)]:
        del os.environ[k]
    os.environ.update(snap)


def scrub_codemonkey_env(extra: Optional[list[str]] = None) -> list[str]:
    """Remove all CODEMONKEY_* (+ listed extras). Returns removed names."""
    removed = [k for k in os.environ if k.startswith(CODEMONKEY_VARS_PREFIX)]
    for k in removed:
        del os.environ[k]
    for k in (extra or []):
        if k in os.environ:
            removed.append(k)
            del os.environ[k]
    return removed


# modules known env-sensitive (A15 sweep-interleave class)
SENSITIVE_MODULES = (
    "test_cache_telemetry", "test_cost", "test_delegate",
    "test_golden", "test_hygiene_6f4",
)


def is_sensitive(module_name: str) -> bool:
    return any(module_name.startswith(m) for m in SENSITIVE_MODULES)
