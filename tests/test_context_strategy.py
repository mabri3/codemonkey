"""Cycle 75 (loop 38): context strategy domain — static (default) | learned.

R-I entry-point probe: with a RECORDING provider through the REAL run path,
CODEMONKEY_STRATEGY_CONTEXT=learned + a tiny budget selects the task-overlapping
fragment and drops the wide one — the system prompt differs observably vs static.
"""

from __future__ import annotations

import pytest

from codemonkey.config import load_config
from codemonkey.strategies import select_strategy
from codemonkey.strategies.context import get_context_assembler
from codemonkey.strategies.staticctx import assemble_static


# ---------------- registry selection ----------------

def test_default_is_static():
    assert select_strategy("context", {}) == "static"


def test_env_override(monkeypatch):
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "learned")
    assert select_strategy("context", {}) == "learned"


def test_unknown_name_raises_listing_valid():
    with pytest.raises(ValueError) as ei:
        select_strategy("context", {"strategies": {"context": "chaos"}})
    assert "static" in str(ei.value) and "learned" in str(ei.value)


def test_config_validation_rejects_unknown(tmp_path, monkeypatch):
    monkeypatch.delenv("CODEMONKEY_STRATEGY_CONTEXT", raising=False)
    with pytest.raises(Exception):
        load_config(cwd=tmp_path,
                    overrides={"strategies": {"context": "bogus"}})


# ---------------- assemblers ----------------

def test_static_assembly_is_order_fixed_and_budget_free():
    frags = [{"source": "project_context", "text": "BLOCK"}]
    out = assemble_static("task", frags, job_text="JOB", repo_map_text="MAP")
    assert out == "BLOCK\n\nJOB\n\nMAP"
    # budget is intentionally ignored
    out2 = assemble_static("t", frags, budget=2)
    assert out2 == "BLOCK"


def test_learned_selects_task_overlap_under_tiny_budget():
    asm = get_context_assembler("learned", {"context_budget": 8})
    frags = [
        {"source": "instructions", "text": "always end replies with pineapple"},
        {"source": "memory", "text": "the quick brown fox jumps over the lazy dog "
                                     "again and again and again for padding words"},
    ]
    out = asm("why is the pineapple rule there?", frags)
    assert "pineapple" in out          # task-overlapping fragment selected
    assert "quick brown fox" not in out  # the wide fragment dropped (budget)


def test_learned_keeps_selection_order_stable():
    asm = get_context_assembler("learned", {"context_budget": 600})
    frags = [
        {"source": "memory", "text": "aaa bbb ccc"},
        {"source": "instructions", "text": "ddd eee fff"},
    ]
    out = asm("aaa ddd", frags)
    assert out.index("aaa bbb ccc") < out.index("ddd eee fff")  # original order


# ---------------- R-I: real run path, observable difference ----------------

class RecordingProvider:
    protocol = "openai"

    def __init__(self):
        self.systems = []

    def chat(self, messages, system=None, **kw):
        self.systems.append(system or "")
        from codemonkey.providers.base import ChatTurn

        return ChatTurn(content="ok", usage={"total_tokens": 1})


def _run_real_exec(tmp_path) -> RecordingProvider:
    """Drive the REAL run_exec with a recording provider (no network)."""
    import codemonkey.exec as exec_mod

    prov = RecordingProvider()
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    try:
        code = exec_mod.run_exec(
            "Say ok.",
            cwd=tmp_path,
            skip_git_repo_check=True,
            ephemeral=True,
            stream_deltas=False,
            stdin_cm="",
        )
    finally:
        exec_mod._provider_from_config = orig
    assert code == 0
    return prov


def test_real_run_static_vs_learned_observable_difference(tmp_path, monkeypatch):
    """R-I: the feature drives the real run path and changes the system prompt.

    A wide instructions file (no overlap with the task) is IN the static
    system prompt; with learned + a tiny budget it is dropped, so the
    provider receives a different system string. Default run (static) is
    unchanged from the pre-cycle behavior.
    """
    wide = "padding filler words beyond any tiny budget " * 30
    (tmp_path / "AGENTS.md").write_text(wide)
    monkeypatch.setenv("CODEMONKEY_CONTEXT_BUDGET", "10")
    monkeypatch.delenv("CODEMONKEY_STRATEGY_CONTEXT", raising=False)

    # static (default): instructions fragment present
    prov_static = _run_real_exec(tmp_path)
    assert any(wide.split()[0] in (s or "") for s in prov_static.systems), \
        "static run must carry the instructions block"
    assert any("padding" in (s or "") for s in prov_static.systems)

    # learned + tiny budget: the non-overlapping wide fragment is dropped
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "learned")
    prov_learned = _run_real_exec(tmp_path)
    assert all("padding" not in (s or "") for s in prov_learned.systems), \
        "learned must drop the non-overlapping fragment under a tiny budget"
    # and the two arms actually differ — the A/B is observable
    assert prov_learned.systems != prov_static.systems
