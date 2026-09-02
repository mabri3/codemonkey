"""Compaction strategies (cycle 7): pluggable, config-selected.

Protocol:
    maybe_compact(messages, budget_tokens, keep=10, provider=None) -> messages

  - summarizing (default): when the estimated token count of the *older*
    messages exceeds 60% of the configured context budget, collapse those
    older messages into a single rolling summary block produced by the active
    provider. Requires `provider` (a provider object with .chat()).
  - sliding-window: keep the last N messages, drop the rest. No LLM call.

Token estimate is a simple len(chars)//4 heuristic; a real tokenizer can be
substituted without changing the protocol.
"""

from __future__ import annotations

from typing import List, Optional


def _estimate_tokens(messages: list) -> int:
    """Cheap char/4 token estimate across all message content strings."""
    total = 0
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, str):
            total += max(1, len(content) // 4)
    return total


class SummarizingCompaction:
    """Rolling-summary compaction via the active provider (default)."""

    name = "summarizing"
    TRIGGER_FRACTION = 0.6

    def __init__(self, context_limit: int = 32000):
        self.context_limit = context_limit

    def maybe_compact(self, messages, budget_tokens=None, keep=10, provider=None):
        budget = budget_tokens or self.context_limit
        if len(messages) <= keep:
            return list(messages)

        # Keep the last `keep` messages verbatim; consider the older tail.
        split = len(messages) - keep
        older = messages[:split]
        recent = messages[split:]

        # Trigger only when older content alone eats >60% of the budget.
        if _estimate_tokens(older) < self.TRIGGER_FRACTION * (budget // 4):
            return list(messages)

        if provider is None:
            # No LLM available: degrade gracefully to a truncated window so we
            # never crash a run because summarization is unavailable.
            return recent

        # Build a compact prompt of the older messages and ask the provider for
        # a rolling summary.
        lines = []
        for m in older:
            role = m.get("role", "unknown")
            body = (m.get("content") or "")[:2000]
            lines.append(f"[{role}] {body}")
        transcript = "\n".join(lines)
        prompt = (
            "Summarize the following coding-agent conversation into a short, "
            "dense brief (goals, decisions, files touched, open work). Keep it "
            "under ~400 tokens.\n\n" + transcript
        )
        try:
            turn = provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a terse technical summarizer. Reply with the brief only.",
            )
            summary = turn.content or "(no summary produced)"
        except Exception:
            # Summarization failed: fall back to the plain window rather than
            # aborting the run.
            return recent

        brief = {"role": "system", "content": f"[prior context]\n{summary}"}
        return [brief] + recent


class SlidingWindowCompaction:
    """Keep the last N messages, drop the rest. No LLM call."""

    name = "sliding-window"

    def __init__(self, keep=10):
        self.keep = keep

    def maybe_compact(self, messages, budget_tokens=None, keep=None, provider=None):
        n = keep if keep is not None else self.keep
        if len(messages) <= n:
            return list(messages)
        return list(messages[-n:])


_COMPACTORS = {
    "summarizing": SummarizingCompaction,
    "sliding-window": SlidingWindowCompaction,
}

VALID_COMPACTORS = sorted(_COMPACTORS)


def get_compactor(name: str, cfg=None):
    """Instantiate a compaction strategy by config name (unknown -> ValueError)."""
    if name not in _COMPACTORS:
        raise ValueError(
            f"unknown compaction strategy '{name}'. "
            f"Valid compaction strategies: {', '.join(VALID_COMPACTORS)}"
        )
    if name == "summarizing":
        limit = (cfg or {}).get("context_limit", 32000)
        return SummarizingCompaction(context_limit=int(limit or 32000))
    return SlidingWindowCompaction(keep=10)

