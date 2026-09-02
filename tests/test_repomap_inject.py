"""Cycle 21 (loop4): repo-map ranking, budget, opt-in injection.

Verify probe (plan.md): >=4 tests — injected block never exceeds the budget;
gate off by default -> absent; recently-committed files rank ahead of stale
ones on a fixture repo; the injected block is identical across two
consecutive turns (feeds cycle-22 prefix stability).
"""

from __future__ import annotations

import subprocess

import pytest

from codemonkey import repomap as rm


@pytest.fixture()
def git_repo(tmp_path):
    def git(*args):
        subprocess.run(["git"] + list(args), cwd=tmp_path,
                       capture_output=True, text=True, check=True)

    git("init", "-q")
    git("config", "user.name", "t")
    git("config", "user.email", "t@t")
    # stale file committed first
    (tmp_path / "stale.py").write_text("def stale_fn():\n    pass\n" * 3)
    git("add", "-A")
    git("commit", "-qm", "stale")
    # recent file committed last (touched most recently)
    (tmp_path / "recent.py").write_text("def recent_fn():\n    pass\n" * 8)
    git("add", "-A")
    git("commit", "-qm", "recent")
    return tmp_path


def test_rank_recent_before_stale(git_repo):
    m = rm.scan_repo(git_repo, use_cache=False)
    ranked = rm.rank_files(m, git_repo)
    assert ranked.index("recent.py") < ranked.index("stale.py")


def test_density_breaks_recency_ties(tmp_path):
    # no git repo: recency all zero -> density decides
    (tmp_path / "small.py").write_text("def one():\n    pass\n")
    (tmp_path / "big.py").write_text("".join(f"def f{i}():\n    pass\n" for i in range(10)))
    m = rm.scan_repo(tmp_path, use_cache=False)
    ranked = rm.rank_files(m, tmp_path)
    assert ranked.index("big.py") < ranked.index("small.py")


def test_injection_never_exceeds_budget(git_repo):
    m = rm.scan_repo(git_repo, use_cache=False)
    for budget in (200, 800, 4000):
        text = rm.render_injection(m, git_repo, budget=budget)
        assert len(text) <= budget
        assert text.startswith("[repo map")


def test_budget_omission_marker(git_repo):
    m = rm.scan_repo(git_repo, use_cache=False)
    text = rm.render_injection(m, git_repo, budget=120)
    assert "omitted by budget" in text


def test_empty_map_renders_empty():
    assert rm.render_injection({}, "/tmp") == ""


# ---------------- exec injection (gated) ----------------

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

    return ToolContext(workdir=tmp, sandbox="read-only", timeout=10)


def test_gate_off_by_default_absent(tmp_path, monkeypatch):
    from codemonkey.loop import run_turns

    (tmp_path / "a.py").write_text("def a():\n    pass\n")
    monkeypatch.delenv("CODEMONKEY_REPO_MAP", raising=False)
    prov = SpyProvider()
    # simulate exec's gate: cfg has no repo_map -> build block without map
    system_extra = "base"
    run_turns(prov, "hi", _ctx(tmp_path), tool_protocol="prompt",
              max_turns=2, system_extra=system_extra)
    assert "[repo map" not in prov.seen[0]["system"]


def test_injection_identical_across_two_turns(tmp_path):
    """Prefix-stability invariant: the same map text is produced on consecutive
    turns (cache + ranking are deterministic)."""
    (tmp_path / "a.py").write_text("def a():\n    pass\n" * 5)
    (tmp_path / "b.py").write_text("def b():\n    pass\n")
    m1 = rm.scan_repo(tmp_path)
    t1 = rm.render_injection(m1, tmp_path, budget=4000)
    m2 = rm.scan_repo(tmp_path)  # cache hit
    t2 = rm.render_injection(m2, tmp_path, budget=4000)
    assert t1 == t2 and t1 != ""
