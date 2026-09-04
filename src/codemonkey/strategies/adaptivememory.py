"""Memory strategy `adaptive` (loop 38, cycle 76).

Wraps FileMemory with adaptivemem selection: the file keeps accumulating
facts (add_contract unchanged), but `load()` returns only the lines selected
by recency-decay scoring under a token budget — keeping prompt injection
bounded instead of growing forever. Default stays `file` (verbatim).
"""

from __future__ import annotations

from .memory import FileMemory


class AdaptiveMemory(FileMemory):
    """FileMemory whose load() applies adaptivemem.adaptive_select."""

    name = "adaptive"

    def __init__(self, path=None, token_budget: int = 300):
        super().__init__(path)
        self.token_budget = int(token_budget or 300)

    def load(self) -> str:
        raw = super().load()
        if not raw:
            return ""
        from .. import adaptivemem

        kept, _dropped = adaptivemem.adaptive_select(
            raw.splitlines(), token_budget=self.token_budget
        )
        return kept
