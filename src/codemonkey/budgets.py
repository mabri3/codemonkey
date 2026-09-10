"""Runtime autonomy budgets (loop44, cycle 103).

BEFORE THIS CYCLE a "budget" in this repo was a REPORT. `budget.py` computes a
context size from VRAM, `cost.py` tallies spend after the fact, and the loop-39
`RecoveryTracker` counts turns *after the first error* — none of them stop a
running agent. This module makes a declared budget a LIMIT: the run halts at
the boundary rather than degrading past it, and says which boundary it hit.

Two things this module is careful about:

1. **An unset field means UNLIMITED, and it is stated.** `None` is not zero.
   A run with no declared budget behaves exactly as before this cycle (the
   whole capability is opt-in), and `describe()` prints `unlimited` rather
   than an empty string, so a report can never imply a limit that is not
   there.
2. **A self-authored rule may NARROW a budget, never widen one** (R44 ASK 3:
   "No self-authored rule may ever raise a budget. Rejections recorded"). The
   refusal is a control with a break-verified test, not a comment.

Distinct from the loop-39 recovery budget on purpose: that one is a post-error
heuristic emitting `failure_report.budget_exhausted`; this one is a declared,
pre-run contract emitting `budget.exhausted` and exit code 4 (contract §1/§2).
Conflating them would have made two different claims share one control.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, NamedTuple, Optional

FIELDS: tuple[str, ...] = ("turns", "tokens", "seconds", "files")

# What each field counts, in the words a report can quote.
FIELD_MEANING = {
    "turns": "model turns started",
    "tokens": "total tokens billed across turns",
    "seconds": "wall-clock seconds since the run began",
    "files": "distinct paths written by this run",
}


class Refused(NamedTuple):
    """A proposal that would have WIDENED a budget, and why it was refused."""
    field: str
    declared: Any
    proposed: Any
    reason: str


@dataclass
class Declared:
    """The budget a run was started with. `None` on a field = unlimited."""

    turns: Optional[int] = None
    tokens: Optional[int] = None
    seconds: Optional[float] = None
    files: Optional[int] = None

    @classmethod
    def from_config(cls, cfg: Optional[dict]) -> "Declared":
        raw = ((cfg or {}).get("budgets") or {}) if isinstance(cfg, dict) else {}
        return cls(
            turns=_positive_int(raw.get("turns")),
            tokens=_positive_int(raw.get("tokens")),
            seconds=_positive_float(raw.get("seconds")),
            files=_positive_int(raw.get("files")),
        )

    def as_dict(self) -> dict:
        return {f: getattr(self, f) for f in FIELDS}

    def is_unlimited(self) -> bool:
        return all(getattr(self, f) is None for f in FIELDS)

    def describe(self) -> str:
        if self.is_unlimited():
            return "unlimited (no budget declared)"
        parts = [f"{f}={getattr(self, f)}" for f in FIELDS
                 if getattr(self, f) is not None]
        return ", ".join(parts)


class Breach(NamedTuple):
    field: str
    limit: float
    observed: float
    turn: int
    declared: dict

    def as_event(self) -> dict:
        """The `budget.exhausted` payload (contract §2)."""
        return {
            "type": "budget.exhausted",
            "field": self.field,
            "limit": self.limit,
            "observed": self.observed,
            "turn": self.turn,
            "declared": self.declared,
            "meaning": FIELD_MEANING.get(self.field, self.field),
        }

    def closing(self) -> str:
        """The honest closing line, for stdout (C91 precedent)."""
        return (f"BUDGET REACHED — {self.field} limit {self.limit} "
                f"({FIELD_MEANING.get(self.field, self.field)}); observed "
                f"{self.observed} at turn {self.turn}. The run stopped itself "
                f"before crossing the limit. Declared: "
                f"{', '.join(f'{k}={v}' for k, v in self.declared.items() if v is not None)}. "
                f"Resume from the job file, or re-run with a deliberately "
                f"raised budget.")


class BudgetTracker:
    """Observes a run and reports the FIRST limit it crosses.

    Deterministic order (FIELDS) so two runs breaching at the same moment
    report the same field.
    """

    def __init__(self, declared: Declared, *, clock: Callable[[], float] = time.monotonic):
        self.declared = declared
        self._clock = clock
        self._t0 = clock()
        self.turn = 0
        self.tokens = 0
        self.files = 0
        self._paths: set[str] = set()
        self.breach: Optional[Breach] = None

    # ---- observation ----------------------------------------------------
    def begin_turn(self) -> Optional[Breach]:
        """Called before each turn. Enforces turns + wall-clock, which are
        knowable BEFORE the turn's cost is spent — that is the whole point of
        a budget: stop at the boundary, do not cross it and then report."""
        self.turn += 1
        return self._check()

    def note_tokens(self, total: int) -> Optional[Breach]:
        try:
            self.tokens = max(self.tokens, int(total))
        except (TypeError, ValueError):
            pass
        return self._check()

    def note_path(self, path: str) -> Optional[Breach]:
        """A written path. Mutating shell calls with unknown targets pass a
        synthetic key so the budget still bites."""
        if path:
            self._paths.add(str(path))
        self.files = len(self._paths)
        return self._check()

    def note_unknown_write(self, key: str) -> Optional[Breach]:
        return self.note_path(f"<shell-mediated:{key}>")

    # ---- reporting ------------------------------------------------------
    def elapsed(self) -> float:
        return max(0.0, self._clock() - self._t0)

    def _check(self) -> Optional[Breach]:
        if self.breach is not None:
            return self.breach           # first breach wins, reported once
        observed = {"turns": self.turn, "tokens": self.tokens,
                    "seconds": self.elapsed(), "files": self.files}
        for field in FIELDS:
            limit = getattr(self.declared, field)
            if limit is None:
                continue
            if observed[field] > limit:
                self.breach = Breach(field=field, limit=limit,
                                     observed=round(observed[field], 3),
                                     turn=self.turn,
                                     declared=self.declared.as_dict())
                return self.breach
        return None

    def report(self) -> dict:
        return {
            "declared": self.declared.as_dict(),
            "description": self.declared.describe(),
            "observed": {"turns": self.turn, "tokens": self.tokens,
                         "seconds": round(self.elapsed(), 3), "files": self.files},
            "breach": self.breach._asdict() if self.breach else None,
        }


def check_proposal(declared: Declared, proposal: dict) -> tuple[Declared, list[Refused]]:
    """Apply a proposed budget change; REFUSE anything that widens.

    R44 ASK 3, verbatim: *"No self-authored rule may ever raise a budget.
    Rejections recorded."* A proposal may narrow a limit, add a limit where
    there was none, or leave it alone. It may not raise one, and it may not
    clear one back to unlimited — `None` is the widest value there is.

    Returns the (possibly narrowed) budget and every refusal, so the caller
    can journal them. Refusals are the point: a silent no-op would leave the
    proposal looking as though it had been applied.
    """
    out = Declared(**declared.as_dict())
    refused: list[Refused] = []
    for field, proposed in (proposal or {}).items():
        if field not in FIELDS:
            continue
        current = getattr(out, field)
        if proposed is None:
            if current is not None:
                refused.append(Refused(
                    field, current, None,
                    "clearing a limit widens it to unlimited — refused"))
            continue
        if not _is_positive_number(proposed):
            refused.append(Refused(
                field, current, proposed,
                f"not a positive number: {proposed!r} — refused"))
            continue
        if current is None:
            setattr(out, field, proposed)       # adding a limit narrows
            continue
        if proposed > current:
            refused.append(Refused(
                field, current, proposed,
                f"raising {field} from {current} to {proposed} widens the "
                f"budget — refused"))
            continue
        setattr(out, field, proposed)
    return out, refused


def apply_self_authored(declared: Declared, rule: dict) -> tuple[Declared, list[Refused]]:
    """Route a self-authored rule's budget effect through the invariant.

    A rule that carries no budget keys is a no-op here (it cannot raise a
    budget it does not mention). A rule that carries them is checked exactly
    like any other proposal.
    """
    return check_proposal(declared, (rule or {}).get("budgets") or {})


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _positive_int(value: Any) -> Optional[int]:
    if not _is_positive_number(value):
        return None
    return int(value)


def _positive_float(value: Any) -> Optional[float]:
    if not _is_positive_number(value):
        return None
    return float(value)
