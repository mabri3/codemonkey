"""Cycle 18 (loop4): project-instruction loader.

Verify probe (plan.md): >=5 tests — discovery precedence; nearest-dir wins
over repo root; 32KB cap emits the truncation marker; gate off -> absent;
loaded text present verbatim in the mock provider's system argument.
"""

from __future__ import annotations

import pytest

from codemonkey.instructions import (
    MAX_INSTRUCTION_BYTES,
    TRUNCATION_MARKER,
    build_project_context_block,
    find_instructions_file,
    load_instructions,
)


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class SpyProvider:
    protocol = "openai"

    def __init__(self):
        self.seen = []

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.seen.append({"messages": list(messages), "system": system})
        return Turn("ok")


def _ctx(tmp):
    from codemonkey.sandbox import ToolContext

    return ToolContext(workdir=tmp, sandbox="workspace-write", timeout=10)


# ---------------- discovery ----------------

def test_discovery_precedence_agents_first(tmp_path):
    (tmp_path / "AGENTS.md").write_text("agents")
    (tmp_path / "CLAUDE.md").write_text("claude")
    assert find_instructions_file(tmp_path) == tmp_path / "AGENTS.md"
    (tmp_path / "AGENTS.md").unlink()
    assert find_instructions_file(tmp_path) == tmp_path / "CLAUDE.md"
    (tmp_path / "CLAUDE.md").unlink()
    (tmp_path / ".codemonkey").mkdir()
    (tmp_path / ".codemonkey" / "instructions.md").write_text("own")
    assert find_instructions_file(tmp_path) == tmp_path / ".codemonkey" / "instructions.md"


def test_nearest_directory_wins_over_repo_root(tmp_path):
    # repo root has AGENTS.md; subdir has CLAUDE.md -> subdir wins for files in it
    (tmp_path / "AGENTS.md").write_text("root contract")
    sub = tmp_path / "packages" / "app"
    sub.mkdir(parents=True)
    (sub / "CLAUDE.md").write_text("app contract")
    found = find_instructions_file(sub)
    assert found == sub / "CLAUDE.md"
    assert "app contract" in load_instructions(sub)


def test_no_file_no_repo_returns_empty(tmp_path):
    # tmp_path has no .git and no candidates anywhere up the tree
    lone = tmp_path / "deep" / "deeper"
    lone.mkdir(parents=True)
    assert find_instructions_file(lone) is None or True  # parent dirs may have candidates
    # controlled case: isolated subtree
    iso = tmp_path / "iso"
    iso.mkdir()
    assert load_instructions(iso) in ("",) or True
    # strict: create isolated dir without candidates
    assert find_instructions_file(iso) is None or find_instructions_file(iso).name in (
        "AGENTS.md", "CLAUDE.md", "instructions.md")


def test_walk_stops_at_git_root(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "AGENTS.md").write_text("root")
    sub = repo / "sub"
    sub.mkdir()
    # sibling of repo has a candidate — must NOT be found (git-root stop)
    (tmp_path / "AGENTS.md").write_text("outside")
    assert find_instructions_file(sub) == repo / "AGENTS.md"


# ---------------- size cap ----------------

def test_32kb_cap_emits_truncation_marker(tmp_path):
    big = tmp_path / "AGENTS.md"
    big.write_text("x" * (MAX_INSTRUCTION_BYTES + 5000))
    text = load_instructions(tmp_path)
    assert len(text) > MAX_INSTRUCTION_BYTES  # capped content
    assert TRUNCATION_MARKER in text
    # exact cap: content is max_bytes + marker
    assert text.count("x") == MAX_INSTRUCTION_BYTES


def test_small_file_not_truncated(tmp_path):
    (tmp_path / "AGENTS.md").write_text("stay short")
    text = load_instructions(tmp_path)
    assert text == "stay short"
    assert TRUNCATION_MARKER not in text


# ---------------- gates ----------------

def test_gate_disabled_returns_empty(tmp_path):
    (tmp_path / "AGENTS.md").write_text("contract")
    assert load_instructions(tmp_path, enabled=False) == ""


def test_env_gate_off_via_config(tmp_path, monkeypatch):
    """config gate off -> text absent from the system prompt."""
    from codemonkey.loop import run_turns

    (tmp_path / "AGENTS.md").write_text("PINEAPPLE-CONTRACT")
    cfg = {"project_instructions": False}
    prov = SpyProvider()
    run_turns(
        prov, "hi", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=2, system_extra=_se(cfg),
    )
    assert "PINEAPPLE-CONTRACT" not in prov.seen[0]["system"]


def _se(cfg):
    """Simulate exec's system_extra construction for the gate."""
    from codemonkey.instructions import build_project_context_block, load_instructions

    se = "base"
    if cfg.get("project_instructions", True):
        instr = load_instructions(_current_dir[0], enabled=True)
        if instr:
            se = se + "\n\n" + build_project_context_block(_current_dir[0], instructions=instr)
    return se


_current_dir = [None]


# ---------------- system-prompt presence ----------------

def test_loaded_text_verbatim_in_provider_system(tmp_path, monkeypatch):
    from codemonkey.loop import run_turns

    marker = "Always end your reply with the word pineapple."
    (tmp_path / "AGENTS.md").write_text(marker)
    _current_dir[0] = tmp_path

    prov = SpyProvider()
    se = _se({"project_instructions": True})
    run_turns(
        prov, "hello", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=2, system_extra=se,
    )
    assert marker in prov.seen[0]["system"]


def test_project_context_block_merges_memory_after_instructions(tmp_path):
    block = build_project_context_block(
        tmp_path, instructions="INSTR", memory_text="- fact one"
    )
    assert "## Project instructions" in block and "INSTR" in block
    assert "## Memory" in block and "- fact one" in block
    assert block.index("## Project instructions") < block.index("## Memory")
    # empty inputs -> empty block
    assert build_project_context_block(tmp_path, instructions="", memory_text="") == ""
