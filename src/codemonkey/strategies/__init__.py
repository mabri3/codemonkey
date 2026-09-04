"""Strategy registries (cycle 7).

Config-selected, env-overridable, pluggable by domain:
  - compaction:    summarizing (default) | sliding-window
  - memory:        file (default)        | none
  - session_state: jsonl (default)       | sqlite

Selector precedence: CODEMONKEY_STRATEGY_<DOMAIN> env var > strategies.<domain>
in config > default. Unknown names raise ValueError; the CLI surface maps that
to exit 2 with the valid names listed (A19).
"""

from __future__ import annotations

import os
from typing import Optional

from .compaction import get_compactor, VALID_COMPACTORS
from .memory import get_memory, VALID_MEMORY
from .session_state import get_store, VALID_STORES
from .context import get_context_assembler, VALID_CONTEXT

DOMAINS = {
    "compaction": {"env": "CODEMONKEY_STRATEGY_COMPACTION", "valid": VALID_COMPACTORS, "default": "summarizing"},
    "memory": {"env": "CODEMONKEY_STRATEGY_MEMORY", "valid": VALID_MEMORY, "default": "file"},
    "session_state": {"env": "CODEMONKEY_STRATEGY_SESSION_STATE", "valid": VALID_STORES, "default": "jsonl"},
    "context": {"env": "CODEMONKEY_STRATEGY_CONTEXT", "valid": VALID_CONTEXT, "default": "static"},
}


class StrategyError(ValueError):
    """Unknown strategy name (CLI maps this to exit 2)."""


def select_strategy(domain: str, cfg: Optional[dict] = None) -> str:
    """Resolve the effective strategy name for a domain.

    Precedence: CODEMONKEY_STRATEGY_<DOMAIN> env > strategies.<domain> config
    > default. Raises StrategyError (exit-2 surface) listing valid names.
    """
    if domain not in DOMAINS:
        raise StrategyError(f"unknown strategy domain '{domain}'. "
                            f"Valid domains: {', '.join(sorted(DOMAINS))}")
    meta = DOMAINS[domain]
    name = os.environ.get(meta["env"])
    if name is None:
        name = ((cfg or {}).get("strategies") or {}).get(domain)
    if name is None:
        return meta["default"]
    name = str(name)
    if name not in meta["valid"]:
        raise StrategyError(
            f"unknown {domain} strategy '{name}'. "
            f"Valid {domain} strategies: {', '.join(meta['valid'])}"
        )
    return name


def build(cfg: Optional[dict] = None):
    """Build the full effective strategy bundle from a config dict.

    Returns {"compaction": <strat>, "memory": <strat>, "session_state": <store>}.
    """
    cfg = cfg or {}
    compaction_name = select_strategy("compaction", cfg)
    memory_name = select_strategy("memory", cfg)
    session_name = select_strategy("session_state", cfg)
    return {
        "compaction": get_compactor(compaction_name, cfg),
        "memory": get_memory(memory_name),
        "session_state": get_store(session_name),
    }

