"""Cycle 97 (loop 41, R41 ASK 1+2): plan object + atomic apply/rollback.

R-I charter probe: a scripted run that writes mid-plan then declares
failure leaves the tree byte-identical (`git status` clean, `git diff`
empty), and the report names what the plan was. Controls: success lands
whole; max_turns ends WITHOUT rollback (resume expects files); shell
during a plan is counted, not covered.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from codemonkey import changeplan as pl_mod


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path


class _Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


def _tool(name, args):
    import json
    return _Turn("TOOL_CALL: " + json.dumps({"name": name, "arguments": args}) + "\n")


class _StuckAfterWritesProv:
    """Writes A (new), overwrites C (existing), writes B (new), then the
    same failing shell call until the policy gives up."""
    protocol = "prompt"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            return _tool("write_file", {"path": "a.txt", "content": "aaa"})
        if self.n == 2:
            return _tool("write_file", {"path": "c.txt", "content": "changed"})
        if self.n == 3:
            return _tool("write_file", {"path": "b.txt", "content": "bbb"})
        return _tool("shell", {"command": "exit 1"})

    def close(self):
        pass


def _git_clean(workdir):
    if shutil.which("git") is None:
        pytest.skip("git not available")
    subprocess.run(["git", "init", "-q"], cwd=workdir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=workdir, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "pre"], cwd=workdir, check=True)
    out = subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                         capture_output=True, text=True, check=True)
    return out.stdout


def _run(home_dir, name, prov, max_turns=12, **kw):
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    workdir = home_dir / name
    workdir.mkdir()
    (workdir / "c.txt").write_text("orig")
    _git_clean(workdir)
    events: list = []
    ctx = ToolContext(workdir=workdir, sandbox="danger-full-access")
    turn = run_turns(prov, "do the writes", ctx,
                     tool_protocol="prompt", max_turns=max_turns,
                     journal_thread=f"ws-{name}", journal_run="r1",
                     redact_needles=[], atomic_plan=True,
                     on_event=events.append, **kw)
    return workdir, turn, events


def test_gave_up_rolls_back_whole_tree_byte_identical(home):
    workdir, turn, events = _run(home, "ws-fail", _StuckAfterWritesProv())
    assert getattr(turn, "gave_up", None), "run must declare failure"
    rb = turn.gave_up.get("plan_rollback")
    assert rb, "report must carry the rollback"
    assert rb["plan_id"] and rb["workdir"] == str(workdir.resolve())
    assert rb["rollback"]["removed"] == ["a.txt", "b.txt"]
    assert rb["rollback"]["restored"] == ["c.txt"]
    assert not (workdir / "a.txt").exists()
    assert not (workdir / "b.txt").exists()
    assert (workdir / "c.txt").read_text() == "orig"
    status = subprocess.run(["git", "status", "--porcelain"], cwd=workdir,
                            capture_output=True, text=True, check=True).stdout
    assert status == "", "tree must be byte-identical to pre-plan state"
    diff = subprocess.run(["git", "diff"], cwd=workdir,
                          capture_output=True, text=True, check=True).stdout
    assert diff == ""
    kinds = [e["type"] for e in events]
    assert "plan.started" in kinds and "plan.rolled_back" in kinds
    rolled = next(e for e in events if e["type"] == "plan.rolled_back")
    assert rolled["report"]["plan_id"] == rb["plan_id"]
    assert rolled["report"]["files"] == ["a.txt", "b.txt", "c.txt"]


def test_success_lands_whole(home):
    class _Ok:
        protocol = "prompt"

        def __init__(self):
            self.n = 0

        def chat(self, messages, system=None, **kw):
            self.n += 1
            if self.n == 1:
                return _tool("write_file", {"path": "a.txt", "content": "aaa"})
            return _Turn("done")

        def close(self):
            pass

    workdir, turn, events = _run(home, "ws-ok", _Ok())
    assert not getattr(turn, "gave_up", None)
    assert (workdir / "a.txt").read_text() == "aaa"
    done = next(e for e in events if e["type"] == "plan.completed")
    assert done["report"]["files"] == ["a.txt"]
    assert "plan.rolled_back" not in [e["type"] for e in events]


def test_max_turns_ends_plan_without_rollback(home):
    class _Never:
        protocol = "prompt"

        def chat(self, messages, system=None, **kw):
            return _tool("write_file", {"path": "a.txt", "content": "aaa"})

        def close(self):
            pass

    workdir, turn, events = _run(home, "ws-max", _Never(), max_turns=2)
    assert (workdir / "a.txt").exists(), "resume expects files present"
    kinds = [e["type"] for e in events]
    assert "plan.completed" in kinds and "plan.rolled_back" not in kinds


def test_shell_counted_not_covered(home):
    class _ShellThenDone:
        protocol = "prompt"

        def __init__(self):
            self.n = 0

        def chat(self, messages, system=None, **kw):
            self.n += 1
            if self.n == 1:
                return _tool("shell", {"command": "echo hi"})
            return _Turn("done")

        def close(self):
            pass

    _, _, events = _run(home, "ws-shell", _ShellThenDone())
    done = next(e for e in events if e["type"] == "plan.completed")
    assert done["report"]["shell_calls_during_plan"] == 1
    assert done["report"]["shell_covered"] is False


def test_first_write_wins_and_created_deleted(home):
    from pathlib import Path

    plan = pl_mod.begin_plan(home)
    try:
        pl_mod.note_write(plan, home, "f.txt", b"v1")
        pl_mod.note_write(plan, home, "f.txt", b"v2")  # ignored
        pl_mod.note_write(plan, home, "new.txt", None)
        (home / "f.txt").write_text("v2")
        (home / "new.txt").write_text("n")
        try:
            pl_mod.end_plan()
            res = pl_mod.rollback_plan(plan, home)
        finally:
            pass
        assert res["restored"] == ["f.txt"] and res["removed"] == ["new.txt"]
        assert (home / "f.txt").read_bytes() == b"v1"
        assert not (home / "new.txt").exists()
    finally:
        if pl_mod.current_plan() is plan:
            pl_mod.end_plan()


def test_workdir_mismatch_refused(home, tmp_path):
    plan = pl_mod.begin_plan(home)
    try:
        other = tmp_path / "elsewhere"
        other.mkdir()
        with pytest.raises(ValueError, match="belongs to"):
            pl_mod.rollback_plan(plan, other)
    finally:
        if pl_mod.current_plan() is plan:
            pl_mod.end_plan()


def test_persisted_plan_reloads_for_crash_recovery(home):
    plan = pl_mod.begin_plan(home)
    pl_mod.note_write(plan, home, "f.txt", b"v1")
    pid = plan.plan_id
    pl_mod.end_plan()
    loaded = pl_mod.load_plan(pid)
    assert loaded.files == {"f.txt": {"existed": True}}
    assert any(p["plan_id"] == pid for p in pl_mod.list_plans())


# ---------------- 97F1: mixed-tree honesty ----------------

class _MixedProv:
    """write_file lands, shell heredoc lands, then the same failing call
    until the policy gives up."""
    protocol = "prompt"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            return _tool("write_file", {"path": "a.txt", "content": "aaa"})
        if self.n == 2:
            return _tool("shell", {"command": "printf 'sh' > s.txt"})
        return _tool("shell", {"command": "exit 1"})

    def close(self):
        pass


class _CleanShellProv:
    """write_file lands, NON-mutating shell only, then stuck."""
    protocol = "prompt"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            return _tool("write_file", {"path": "a.txt", "content": "aaa"})
        if self.n == 2:
            return _tool("shell", {"command": "echo hello"})
        return _tool("shell", {"command": "exit 1"})

    def close(self):
        pass


def test_mixed_tree_names_shell_path_in_report_and_closing(home):
    workdir, turn, events = _run(home, "ws-mixed", _MixedProv())
    assert getattr(turn, "gave_up", None), "run must declare failure"
    assert not (workdir / "a.txt").exists(), "tracked edit reverted"
    assert (workdir / "s.txt").read_text() == "sh", "shell file remains"
    rb = turn.gave_up["plan_rollback"]
    assert rb["shell_uncovered_paths"] == ["s.txt"]
    assert rb["shell_mutating_calls"] == 1
    closing = turn.gave_up["closing"]
    assert "s.txt" in closing and "OUTSIDE" in closing, closing
    rolled = next(e for e in events if e["type"] == "plan.rolled_back")
    assert rolled["report"]["shell_uncovered_paths"] == ["s.txt"]


def test_non_mutating_shell_raises_no_warning(home):
    # 91F1 lesson as discriminator: grep/ls/echo must NOT arm the warning.
    workdir, turn, events = _run(home, "ws-clean", _CleanShellProv())
    assert getattr(turn, "gave_up", None)
    rb = turn.gave_up["plan_rollback"]
    assert rb["shell_mutating_calls"] == 0
    assert rb["shell_uncovered_paths"] == []
    assert "OUTSIDE" not in turn.gave_up["closing"]
    assert (workdir / "a.txt").exists() is False


def test_note_shell_lists_only_mutating(home):
    plan = pl_mod.begin_plan(home)
    try:
        pl_mod.note_shell(plan, "printf x > s.txt")
        pl_mod.note_shell(plan, "ls -la")
        pl_mod.note_shell(plan, "")
        assert plan.shell_calls == 3
        assert len(plan.shell_mutating) == 1
        assert plan.shell_mutating[0]["pattern"] == "redirect"
        assert plan.shell_mutating[0]["targets"] == ["s.txt"]
        rep = pl_mod.plan_report(plan)
        assert rep["shell_uncovered_paths"] == ["s.txt"]
        assert rep["shell_mutating_calls"] == 1
        import json
        raw = (plan.group_dir / "plan.json").read_text()
        assert "printf" not in raw, "raw command text must not persist"
    finally:
        if pl_mod.current_plan() is plan:
            pl_mod.end_plan()
