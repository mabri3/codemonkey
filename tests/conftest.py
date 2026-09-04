
"""Shared test fixtures/markers (loop7).

Live-LLM tests (ones that subprocess the CLI against the home server) skip
when the home server is unreachable at the network level — an environment
condition, not a code defect. The 6F4 hygiene guard handles its own skip.
"""

import os

import httpx
import pytest

# loop16 addendum: the operator keeps the server key in the repo .env (git-
# ignored). Tests rely on exec loading it; give the whole test session env
# parity (without printing values).
def _load_dotenv_once():
    from pathlib import Path

    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

_load_dotenv_once()

HOME_BASE = "http://192.168.50.176:8080/v1"


def _home_reachable() -> bool:
    if os.environ.get("CODEMONKEY_FORCE_LIVE"):
        return True
    try:
        httpx.post(
            f"{HOME_BASE}/chat/completions",
            json={"model": "unsloth/Qwen3.8-27B-GGUF",
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


# loop23 cycle 60: env quarantine for env-sensitive modules (A15 class)
import pytest as _pytest


@pytest.fixture(autouse=True)
def _quarantine_codemonkey_env(request):
    from codemonkey.envquarantine import (is_sensitive, restore_codemonkey_env,
                                          snapshot_codemonkey_env)

    snap = snapshot_codemonkey_env()
    yield
    restore_codemonkey_env(snap)


@pytest.fixture()
def scrubbed_env():
    from codemonkey.envquarantine import scrub_codemonkey_env

    removed = scrub_codemonkey_env()
    yield removed
