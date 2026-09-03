"""CYCLE 31F1 (critic-loop8 finding 2): the execution journal is wired.

Before this cycle no production caller passed `journal_thread`, so the whole
loop-7 stack (journal, idempotent replay, forensics CLI, eval journal stats)
was inert outside the unit tests. These tests pin the wiring AND the run
scoping that makes cross-invocation replay impossible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codemonkey.journal import args_key, list_threads, read_thread

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def jhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def _patch_tool_provider(monkeypatch, tool_call: str):
    """exec provider that calls one tool, then answers."""
    from codemonkey import exec as exec_mod
    from codemonkey.providers.base import ChatTurn

    n = {"i": 0}

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            n["i"] += 1
            if n["i"] == 1:
                return ChatTurn(content=tool_call, usage={})
            return ChatTurn(content="done", usage={})

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    return exec_mod


def _exec_once(exec_mod, prompt, cwd, **kw):
    sink: list = []
    code = exec_mod.run_exec(
        prompt, cwd=cwd, skip_git_repo_check=True, stream_deltas=False,
        stdin_cm="", event_sink=sink, approval="never",
        sandbox="workspace-write", **kw,
    )
    assert code == 0
    tid = next(e["thread_id"] for e in sink if e.get("type") == "thread.started")
    return tid


def test_exec_run_writes_journal_records(jhome, tmp_path, monkeypatch):
    work = tmp_path / "w"
    work.mkdir()
    (work / "f.txt").write_text("hello")
    exec_mod = _patch_tool_provider(
        monkeypatch, 'TOOL_CALL: {"name": "read_file", "arguments": {"path": "f.txt"}}\n'
    )
    tid = _exec_once(exec_mod, "read it", work)
    recs = read_thread(tid)
    kinds = [(r["type"], r["tool"]) for r in recs]
    assert ("intent", "read_file") in kinds
    assert ("outcome", "read_file") in kinds


def test_journal_thread_is_listed_after_an_exec_run(jhome, tmp_path, monkeypatch):
    work = tmp_path / "w"
    work.mkdir()
    (work / "f.txt").write_text("hello")
    exec_mod = _patch_tool_provider(
        monkeypatch, 'TOOL_CALL: {"name": "read_file", "arguments": {"path": "f.txt"}}\n'
    )
    tid = _exec_once(exec_mod, "read it", work)
    assert tid in list_threads()


def test_run_scope_changes_the_idempotency_key():
    args = {"path": "a.txt", "content": "x"}
    k_run1 = args_key("t", 1, 0, args, run="aaaa")
    k_run2 = args_key("t", 1, 0, args, run="bbbb")
    assert k_run1 != k_run2
    # unscoped callers (the in-process recovery tests) keep the old key
    assert args_key("t", 1, 0, args) == args_key("t", 1, 0, args, run="")


def test_resumed_run_rewrites_instead_of_replaying(jhome, tmp_path, monkeypatch):
    """Two invocations on ONE thread must not replay each other's writes."""
    work = tmp_path / "w"
    work.mkdir()
    call = ('TOOL_CALL: {"name": "write_file", "arguments": '
            '{"path": "out.txt", "content": "written"}}\n')
    exec_mod = _patch_tool_provider(monkeypatch, call)
    tid = _exec_once(exec_mod, "write it", work)
    assert (work / "out.txt").read_text() == "written"

    (work / "out.txt").unlink()  # e.g. the user undid the change
    exec_mod = _patch_tool_provider(monkeypatch, call)
    _exec_once(exec_mod, "write it again", work, resume_thread=tid)
    # a stale cross-run replay would leave the file missing
    assert (work / "out.txt").read_text() == "written"
    assert not any(r.get("status") == "replayed" for r in read_thread(tid))


def test_same_run_replay_still_hits(jhome, tmp_path):
    """The cycle-32 in-run replay contract is unchanged for unscoped callers."""
    from codemonkey.journal import find_outcome, record

    record("t-same", "outcome", tool="write_file",
           key=args_key("t-same", 1, 0, {"path": "a"}), status="ok",
           output="wrote 1 bytes")
    hit = find_outcome("t-same", args_key("t-same", 1, 0, {"path": "a"}))
    assert hit and hit["output"] == "wrote 1 bytes"


def test_eval_results_carry_journal_stats(jhome, tmp_path, monkeypatch):
    """eval derives the journal thread from the run's own thread.started."""
    from codemonkey import eval as eval_mod
    from codemonkey.journal import record

    suite = tmp_path / "s.yaml"
    suite.write_text(
        "name: t\ntasks:\n  - id: one\n    prompt: hi\n    expect:\n"
        "      exit_code: 0\n"
    )

    def fake_exec(prompt, **kw):
        sink = kw.get("event_sink")
        sink.append({"type": "thread.started", "thread_id": "t-eval"})
        record("t-eval", "outcome", tool="shell", key="k", status="error",
               error_class="timeout")
        sink.append({"type": "item.completed",
                     "item": {"type": "agent_message", "text": "hi"}})
        return 0

    results = eval_mod.run_suite(suite, exec_fn=fake_exec)
    task = results["tasks"][0]
    assert task["journal_thread"] == "t-eval"
    assert task["journal_classes"] == {"timeout": 1}


def test_repl_turn_journals(jhome, tmp_path, monkeypatch):
    """The REPL is wired too (piped-stdin mode drives one turn)."""
    import io

    from codemonkey import repl as repl_mod
    from codemonkey.providers.base import ChatTurn

    n = {"i": 0}

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            n["i"] += 1
            if n["i"] == 1:
                return ChatTurn(
                    content='TOOL_CALL: {"name": "list_dir", "arguments": {"path": "."}}\n',
                    usage={})
            return ChatTurn(content="done", usage={})

        def close(self):
            pass

    monkeypatch.setattr(repl_mod, "_build_provider", lambda cfg, name: FP())
    monkeypatch.setattr(repl_mod.sys, "stdin", io.StringIO("go\n"))
    monkeypatch.chdir(tmp_path)
    cfg = {"default_provider": "local", "providers": {"local": {"model": "m"}},
           "approval": "never", "sandbox": "workspace-write"}
    repl_mod.run_repl(cfg, stderr=io.StringIO(), stdout=io.StringIO())
    threads = list_threads()
    assert threads, "REPL turn wrote no journal thread"
    assert any(r["tool"] == "list_dir" for t in threads for r in read_thread(t))
