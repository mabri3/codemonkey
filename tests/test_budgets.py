"""loop44 cycle 103 — a declared budget is a LIMIT, and a rule cannot raise one.

Two claims are under test, and the second is the one R44 ASK 3 demanded:

1. A declared budget HALTS the run at the boundary. The evidence that it
   halts *at* the boundary rather than reporting past it is that the provider
   is never called for the turn that would have crossed it.
2. A self-authored rule may narrow a budget and may never widen one. Refusals
   are returned, not silently dropped — a silent no-op would leave the
   proposal looking as though it had been applied.
"""

from __future__ import annotations

import pytest

from codemonkey import budgets
from codemonkey.budgets import (BudgetTracker, Declared, apply_self_authored,
                                check_proposal)
from codemonkey.loop import run_turns
from codemonkey.providers.base import ChatTurn
from codemonkey.sandbox import ToolContext


class ScriptedProv:
    """Counts its calls so a test can prove a turn was never spent."""

    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def chat(self, messages, system=None, **kw):
        self.calls += 1
        idx = min(self.calls - 1, len(self.script) - 1)
        # usage is billed per turn; without it a token budget would never
        # accumulate and the test would pass for the wrong reason.
        return ChatTurn(content=self.script[idx],
                        usage={"total_tokens": 50, "prompt_tokens": 40,
                               "completion_tokens": 10})

    def close(self):
        pass


def _call(name, args) -> str:
    import json as _j
    return "TOOL_CALL: " + _j.dumps({"name": name, "arguments": args})


# ── 1. absence means unlimited, and says so ────────────────────────────────

def test_an_absent_budget_field_is_unlimited_not_zero():
    """The dangerous reading of "no budget" is "budget of zero". A field left
    out must never be treated as a limit that is instantly breached."""
    d = Declared()
    assert d.is_unlimited()
    assert "unlimited" in d.describe()
    t = BudgetTracker(d)
    for _ in range(50):
        assert t.begin_turn() is None
    assert t.note_tokens(10 ** 9) is None
    assert t.breach is None


def test_describe_names_every_declared_limit():
    d = Declared(turns=4, tokens=1000)
    text = d.describe()
    assert "turns=4" in text and "tokens=1000" in text
    assert "seconds" not in text and "files" not in text


# ── 2. the boundary is a boundary ──────────────────────────────────────────

def test_turn_budget_reports_at_the_turn_that_would_cross_it():
    t = BudgetTracker(Declared(turns=2))
    assert t.begin_turn() is None      # turn 1
    assert t.begin_turn() is None      # turn 2 — the last allowed
    b = t.begin_turn()                 # turn 3 would cross
    assert b is not None and b.field == "turns"
    assert b.limit == 2 and b.observed == 3


def test_first_breach_wins_and_is_reported_once():
    t = BudgetTracker(Declared(turns=1, tokens=5))
    t.begin_turn()
    t.note_tokens(99)
    first = t.breach
    assert first is not None
    assert t.note_tokens(10 ** 6) is first      # same breach, not a new one


def test_first_field_in_order_wins_when_two_are_crossed_at_once():
    """Deterministic order — two runs breaching at the same moment must name
    the same field, or the exit reason is unreproducible."""
    t = BudgetTracker(Declared(turns=1, tokens=1))
    t.begin_turn()                       # turn 1 = limit, not yet over
    b = t.note_tokens(50)                # tokens over AND turn 2 pending
    assert b is not None
    t.begin_turn()
    assert t.breach.field == "tokens"


def test_seconds_budget_is_checked_against_the_injected_clock():
    """No sleeping: the clock is injected so wall-clock limits are testable
    deterministically rather than by waiting."""
    now = [0.0]
    t = BudgetTracker(Declared(seconds=10), clock=lambda: now[0])
    assert t.begin_turn() is None
    now[0] = 11.0
    b = t.begin_turn()
    assert b is not None and b.field == "seconds" and b.limit == 10


def test_file_budget_counts_distinct_paths_and_shell_mediated_writes():
    t = BudgetTracker(Declared(files=2))
    assert t.note_path("a.py") is None
    assert t.note_path("a.py") is None      # same path is not a second file
    assert t.files == 1
    assert t.note_path("b.py") is None      # exactly at the limit
    b = t.note_unknown_write("sed -i s/x/y/ c.py")   # shell-mediated
    assert b is not None and b.field == "files" and b.observed == 3


# ── 3. R44 ASK 3: a self-authored rule can never raise a budget ────────────

def test_self_authored_rule_cannot_raise_a_budget():
    """Verbatim ASK 3: "No self-authored rule may ever raise a budget.
    Rejections recorded." """
    declared = Declared(turns=4, tokens=1000)
    narrowed, refused = apply_self_authored(declared, {"budgets": {"turns": 2}})
    assert narrowed.turns == 2
    assert refused == []

    widened, refused2 = apply_self_authored(declared, {"budgets": {"turns": 40}})
    assert widened.turns == 4, "a rule raised the budget"
    assert len(refused2) == 1
    r = refused2[0]
    assert r.field == "turns" and r.declared == 4 and r.proposed == 40
    assert "widen" in r.reason


def test_clearing_a_limit_back_to_unlimited_is_refused():
    """`None` is the widest value there is — dropping a limit is a raise."""
    narrowed, refused = check_proposal(Declared(tokens=100), {"tokens": None})
    assert narrowed.tokens == 100
    assert len(refused) == 1 and "unlimited" in refused[0].reason


def test_adding_a_limit_where_there_was_none_is_allowed():
    """Narrowing an unbounded run is a legitimate proposal."""
    narrowed, refused = check_proposal(Declared(), {"tokens": 5})
    assert narrowed.tokens == 5 and refused == []


def test_a_rule_without_budget_keys_cannot_touch_a_budget():
    declared = Declared(turns=3)
    after, refused = apply_self_authored(
        declared, {"tool": "shell", "pattern": "rm *", "action": "deny"})
    assert after.as_dict() == declared.as_dict() and refused == []


def test_a_nonsense_value_is_refused_rather_than_coerced():
    _, refused = check_proposal(Declared(turns=3), {"turns": "lots"})
    assert len(refused) == 1 and "positive number" in refused[0].reason
    _, refused2 = check_proposal(Declared(turns=3), {"turns": 0})
    assert len(refused2) == 1, "0 is not a limit, it is a hole"


# ── 4. end to end through the loop ─────────────────────────────────────────

def test_run_halts_at_the_declared_turn_budget_without_spending_it(tmp_path):
    prov = ScriptedProv([_call("write_file", {"path": "a.txt", "content": "a"}),
                         _call("write_file", {"path": "b.txt", "content": "b"}),
                         "done"])
    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=30)
    events: list = []
    turn = run_turns(prov, "write two files", ctx, tool_protocol="prompt",
                     max_turns=10, budget=Declared(turns=1),
                     on_event=events.append)

    kinds = [e.get("type") for e in events]
    assert "budget.exhausted" in kinds, kinds
    ev = next(e for e in events if e["type"] == "budget.exhausted")
    assert ev["field"] == "turns" and ev["limit"] == 1 and ev["observed"] == 2
    assert ev["declared"]["turns"] == 1
    assert getattr(turn, "budget_breach", None) is not None
    assert "BUDGET REACHED" in getattr(turn, "budget_closing", "")
    # the boundary is a boundary: turn 2 was never spent on a provider call
    assert prov.calls == 1, f"provider was called {prov.calls} times"
    # and the run did not report a max_turns exhaustion (91F2's lesson)
    assert not any(e.get("type") == "error"
                   and "max_turns" in str(e.get("message", "")) for e in events)


def test_run_without_a_declared_budget_is_unchanged(tmp_path):
    """Opt-in: no budget means no event, no breach, no behavior change."""
    prov = ScriptedProv(["done"])
    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=30)
    events: list = []
    turn = run_turns(prov, "hi", ctx, tool_protocol="prompt", max_turns=3,
                     on_event=events.append)
    assert "budget.exhausted" not in [e.get("type") for e in events]
    assert getattr(turn, "budget_breach", None) is None


def test_token_budget_halts_after_the_turn_that_crossed_it(tmp_path):
    """Tokens are only knowable AFTER a turn is billed, so the halt is one
    turn later than a turn budget — and the report says which."""
    prov = ScriptedProv([_call("write_file", {"path": "a.txt", "content": "a"}),
                         _call("write_file", {"path": "b.txt", "content": "b"}),
                         "done"])
    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=30)
    events: list = []
    turn = run_turns(prov, "go", ctx, tool_protocol="prompt", max_turns=10,
                     budget=Declared(tokens=1), on_event=events.append)
    ev = next(e for e in events if e["type"] == "budget.exhausted")
    assert ev["field"] == "tokens"
    assert getattr(turn, "budget_breach", None)["field"] == "tokens"


def test_config_resolves_budgets_from_env(monkeypatch, tmp_path):
    """The declaration has to be reachable without editing code."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_BUDGET_TURNS", "7")
    monkeypatch.setenv("CODEMONKEY_BUDGET_FILES", "3")
    from codemonkey.config import load_config
    declared = Declared.from_config(load_config(cwd=tmp_path))
    assert declared.turns == 7 and declared.files == 3
    assert declared.tokens is None and declared.seconds is None


def test_exec_maps_a_budget_breach_to_exit_4_and_leaves_a_resume_job(
        monkeypatch, tmp_path):
    """End-to-end at the exec boundary: contract §1 code 4, the §2 event, and
    a resumable job file — because halting honestly means resumable."""
    import codemonkey.exec as exec_mod
    from codemonkey import jobs

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    monkeypatch.setenv("CODEMONKEY_BUDGET_TURNS", "1")
    prov = ScriptedProv([_call("write_file", {"path": "a.txt", "content": "a"}),
                         "done"])
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    monkeypatch.setattr(exec_mod, "_provider_from_config", patched)
    events: list = []
    code = exec_mod.run_exec(
        "write a file", cwd=tmp_path, skip_git_repo_check=True,
        ephemeral=True, stream_deltas=False, stdin_cm="",
        sandbox="workspace-write", approval="never", event_sink=events)

    assert code == 4, f"expected contract §1 code 4, got {code}"
    assert any(e.get("type") == "budget.exhausted" for e in events)
    assert jobs.list_jobs(), "the breach left no resumable job file"
