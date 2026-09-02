"""Cycle 8: approvals layer + review command.

Covers the cycle-8 verify probe (tests/test_approvals.py -q):
  - soft-deny: gated tool NOT dispatched, stderr notice emitted, run CONTINUES
  - approval: never auto-approves
  - bypass flag lifts approvals (and sandbox, tested in exec layer)
  - policies: untrusted gates shell+writes; on-request gates shell only
  - review: diff gathering (uncommitted/base/staged) + one review turn
"""

from __future__ import annotations

import pytest
from codemonkey import approvals as am
from codemonkey.approvals import ALLOW, ASK, SOFT_DENY, decide, tool_result_notice
from codemonkey.loop import run_turns
from codemonkey.providers.base import ChatTurn
from codemonkey.sandbox import ToolContext


# ---------------- policy decisions ----------------

def test_never_auto_approves_everything():
    for tool in ("shell", "write_file", "edit_file", "read_file"):
        d = decide(tool, "never")
        assert d.action == ALLOW


def test_bypass_lifts_approvals():
    for policy in ("untrusted", "on-request"):
        d = decide("shell", policy, bypass=True)
        assert d.action == ALLOW


def test_untrusted_gates_shell_and_writes():
    for tool in ("shell", "write_file", "edit_file"):
        assert decide(tool, "untrusted").action == SOFT_DENY
    # reads stay free
    assert decide("read_file", "untrusted").action == ALLOW


def test_on_request_gates_shell_only():
    assert decide("shell", "on-request").action == SOFT_DENY
    assert decide("write_file", "on-request").action == ALLOW


def test_danger_full_access_preapproves_shell():
    assert decide("shell", "on-request", sandbox="danger-full-access").action == ALLOW


def test_interactive_asks_instead_of_soft_deny():
    assert decide("shell", "on-request", interactive=True).action == ASK


def test_unknown_policy_soft_denies():
    assert decide("shell", "yolo").action == SOFT_DENY


def test_soft_deny_notice_mentions_how_to_allow():
    d = decide("shell", "on-request")
    notice = d.notice
    assert "approval required" in notice
    assert "--approval never" in notice
    assert "dangerously-bypass" in notice


def test_tool_result_notice_tells_model_not_to_retry():
    d = decide("shell", "on-request")
    text = tool_result_notice("shell", d)
    assert "NOT executed" in text
    assert "Do not retry" in text
    assert tool_result_notice("read_file", am.Decision(ALLOW, "")) == ""


# ---------------- loop integration (soft-deny continues the run) ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 0}


class_prov_calls = []


class LoopProvider:
    """First turn: try a gated shell call; second turn: final answer."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, **kw):
        self.calls += 1
        if self.calls == 1:
            content = 'TOOL_CALL: {"name": "shell", "arguments": {"command": "echo hi"}}'
        else:
            content = "done: shell was blocked, answered anyway"
        return Turn(content)


def _ctx(tmp_path):
    return ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)


def test_soft_deny_continues_run(tmp_path, capsys):
    prov = LoopProvider()
    turn = run_turns(
        prov, "do a thing", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="on-request",
    )
    out = capsys.readouterr()
    assert "[codemonkey] approval required" in out.err
    assert out.err.count("--approval never") == 1
    assert turn.content == "done: shell was blocked, answered anyway"


def test_approval_never_runs_the_tool(tmp_path, capsys):
    prov = LoopProvider()
    turn = run_turns(
        prov, "do a thing", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="never",
    )
    out = capsys.readouterr()
    assert "approval required" not in out.err
    assert turn.content == "done: shell was blocked, answered anyway"
    # shell actually executed this time


def test_untrusted_blocks_writes_too(tmp_path, capsys):
    class WriteProvider:
        def __init__(self):
            self.calls = 0

        def chat(self, messages, system=None, tools=None, stream=False,
                 on_token=None, **kw):
            self.calls += 1
            if self.calls == 1:
                return Turn('TOOL_CALL: {"name": "write_file", "arguments": {"path": "x.txt", "content": "hi"}}')
            return Turn("wrote it (not)")

    turn = run_turns(
        WriteProvider(), "write x", _ctx(tmp_path),
        tool_protocol="prompt", max_turns=5, approval="untrusted",
    )
    out = capsys.readouterr()
    assert "approval required" in out.err
    assert not (tmp_path / "x.txt").exists()


# ---------------- review ----------------

class ReviewProvider:
    def __init__(self):
        self.seen = None

    def chat(self, messages, system=None, tools=None, stream=False):
        self.seen = (messages, system)
        return ChatTurn(content="looks fine\nVERDICT: APPROVE")


def test_review_diff_gather_uncommitted(tmp_path):
    import subprocess
    from codemonkey.review import gather_diff, run_review

    def git(*args):
        subprocess.run(["git"] + list(args), cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    git("config", "user.name", "t")
    git("config", "user.email", "t@t")
    (tmp_path / "a.py").write_text("print('v1')\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    (tmp_path / "a.py").write_text("print('v2')\n")

    diff = gather_diff(tmp_path)
    assert "-print('v1')" in diff and "+print('v2')" in diff

    prov = ReviewProvider()
    text = run_review(prov, tmp_path)
    _, system = prov.seen
    assert "senior code reviewer" in system
    assert "VERDICT: APPROVE" in text


def test_review_diff_vs_base(tmp_path):
    import subprocess
    from codemonkey.review import gather_diff

    def git(*args):
        subprocess.run(["git"] + list(args), cwd=tmp_path, capture_output=True, check=True)

    git("init", "-q")
    git("config", "user.name", "t")
    git("config", "user.email", "t@t")
    (tmp_path / "a.py").write_text("one\n")
    git("add", "-A")
    git("commit", "-qm", "c1")
    git("tag", "base")
    (tmp_path / "a.py").write_text("two\n")
    git("add", "-A")
    git("commit", "-qm", "c2")

    diff = gather_diff(tmp_path, base="base")
    assert "-one" in diff and "+two" in diff


def test_review_no_changes_is_error(tmp_path):
    import subprocess
    from codemonkey.review import gather_diff

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "t"], capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@t"], capture_output=True)
    (tmp_path / "a.py").write_text("x\n")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], cwd=tmp_path, capture_output=True)

    with pytest.raises(RuntimeError):
        gather_diff(tmp_path)


def test_review_not_a_git_repo(tmp_path):
    from codemonkey.review import gather_diff

    with pytest.raises(RuntimeError):
        gather_diff(tmp_path)
