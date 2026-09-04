"""Cycle 76 (loop 38): memory strategy `adaptive` — adaptivemem wired as a
selectable strategy (default stays `file`).

R-I entry-point probe: a recording provider through the REAL run path sees
only the budget-selected memory lines.
"""

from __future__ import annotations

import pytest

from codemonkey.strategies import select_strategy
from codemonkey.strategies.memory import get_memory


# ---------------- registry ----------------

def test_default_memory_stays_file():
    assert select_strategy("memory", {}) == "file"


def test_adaptive_selectable_via_env(monkeypatch):
    monkeypatch.setenv("CODEMONKEY_STRATEGY_MEMORY", "adaptive")
    assert select_strategy("memory", {}) == "adaptive"


def test_unknown_memory_exit2_message_lists_adaptive():
    with pytest.raises(ValueError) as ei:
        select_strategy("memory", {"strategies": {"memory": "telepathy"}})
    assert "adaptive" in str(ei.value) and "file" in str(ei.value)


# ---------------- behavior ----------------

def _mem(tmp_path, budget, lines):
    from codemonkey.strategies.adaptivememory import AdaptiveMemory

    m = AdaptiveMemory(tmp_path / "memory.md", token_budget=budget)
    m.path.write_text("\n".join(lines) + "\n")
    return m


def test_round_trip_add_then_load(tmp_path):
    m = get_memory("adaptive", path=tmp_path / "memory.md")
    m.add_fact("likes pineapple on pizza")
    assert "pineapple" in m.load()
    m.add_fact("likes pineapple on pizza")  # idempotent, like FileMemory
    assert m.load().count("pineapple") == 1


def test_budget_honored_and_unselected_absent(tmp_path):
    m = _mem(tmp_path, 3, [
        "alpha bet gamma",
        "delta epsilon zeta",
        "omicron pi rho",
    ])
    out = m.load()
    kept_words = sum(len(l.split()) for l in out.splitlines() if l.strip())
    assert kept_words <= 3  # hard budget: at most the first line's worth
    assert "alpha" in out
    for absent in ("delta", "omicron"):
        assert absent not in out.split()  # word-level, not substring-level


def test_empty_memory_loads_empty(tmp_path):
    from codemonkey.strategies.adaptivememory import AdaptiveMemory

    m = AdaptiveMemory(tmp_path / "mem.md", token_budget=10)
    assert m.load() == ""


# ---------------- R-I: real run path ----------------

class RecordingProvider:
    protocol = "openai"

    def __init__(self):
        self.systems = []

    def chat(self, messages, system=None, **kw):
        self.systems.append(system or "")
        from codemonkey.providers.base import ChatTurn

        return ChatTurn(content="ok", usage={"total_tokens": 1})


def test_real_run_injects_only_selected_lines(tmp_path, monkeypatch):
    """R-I: through the REAL run_exec, adaptive memory injects only the
    selected lines (budget), while `file` would inject everything."""
    import codemonkey.exec as exec_mod

    lines = [f"fact line number {i} about topic-{i}" for i in range(1, 25)]
    fake_home = tmp_path / "home"
    (fake_home / ".codemonkey").mkdir(parents=True)
    (fake_home / ".codemonkey" / "memory.md").write_text("\n".join(lines) + "\n")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("CODEMONKEY_STRATEGY_MEMORY", "adaptive")
    monkeypatch.setenv("CODEMONKEY_MEMORY_TOKEN_BUDGET", "11")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "static")

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
    assert prov.systems, "provider must have received a system prompt"
    sys_text = "\n".join(s or "" for s in prov.systems)
    assert "## Memory" in sys_text
    assert "topic-1" in sys_text         # early line selected (recency)
    # budget is 11 words: one 6-word fact line fits, the second would exceed —
    for i in range(2, 25):
        assert f"topic-{i}" not in sys_text, f"topic-{i} leaked past the budget"


def test_real_run_file_strategy_injects_everything(tmp_path, monkeypatch):
    """The A/B arm: `file` (default) injects all lines — the observable
    difference that makes `adaptive` a real selectable strategy."""
    import codemonkey.exec as exec_mod

    lines = [f"fact line number {i} about topic-{i}" for i in range(1, 25)]
    fake_home = tmp_path / "home"
    (fake_home / ".codemonkey").mkdir(parents=True)
    (fake_home / ".codemonkey" / "memory.md").write_text("\n".join(lines) + "\n")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("CODEMONKEY_STRATEGY_MEMORY", "file")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "static")

    prov = RecordingProvider()
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    try:
        code = exec_mod.run_exec("Say ok.", cwd=tmp_path, skip_git_repo_check=True,
                                 ephemeral=True, stream_deltas=False, stdin_cm="")
    finally:
        exec_mod._provider_from_config = orig
    assert code == 0
    sys_text = "\n".join(s or "" for s in prov.systems)
    assert "topic-24" in sys_text  # file strategy: everything, no budget
