
"""Shared test fixtures/markers (loop7).

Live-LLM tests (ones that subprocess the CLI against the home server) skip
when the home server is unreachable at the network level — an environment
condition, not a code defect. The 6F4 hygiene guard handles its own skip.
"""

import os

import httpx
import pytest

HOME_BASE = "http://192.168.50.113:8080/v1"


def _home_reachable() -> bool:
    if os.environ.get("CODEMONKEY_FORCE_LIVE"):
        return True
    try:
        httpx.post(
            f"{HOME_BASE}/chat/completions",
            json={"model": "Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf",
                  "messages": [{"role": "user", "content": "ping"}], "max_tokens": 8},
            timeout=15,
        )
        return True
    except Exception:
        return False


requires_home = pytest.mark.skipif(
    not _home_reachable(),
    reason="home llama.cpp unreachable (network) — live probe undecidable",
)
