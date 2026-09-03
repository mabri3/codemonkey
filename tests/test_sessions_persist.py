"""CYCLE 7F2 (critic-loop8 finding 1): session persistence is append-only.

The loop returns `history + this run`; persisting that whole stack re-wrote a
resumed thread's history on every resume (2^n growth) and never stored the
final assistant answer. These tests pin the corrected contract:
one run appends exactly its own new messages plus one closing assistant turn.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

SCHEMA = {
    "type": "object",
    "properties": {"project_name": {"type": "string"}},
    "required": ["project_name"],
}


@pytest.fixture()
def tmp_sessions(monkeypatch, tmp_path):
    from codemonkey import sessions as sess

    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    monkeypatch.setattr(sess, "sessions_dir", lambda: sess_dir)
    inst = sess.SessionStore()
    monkeypatch.setattr(sess, "store", lambda cfg=None, _i=inst: _i)
    return inst


def _patch_provider(monkeypatch, answers):
    """Provider returning `answers` in order (last one repeats)."""
    from codemonkey import exec as exec_mod
    from codemonkey.providers.base import ChatTurn

    state = {"n": 0}

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            i = min(state["n"], len(answers) - 1)
            state["n"] += 1
            return ChatTurn(content=answers[i], usage={})

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    return exec_mod, state


def _run(exec_mod, prompt, **kw):
    sink: list = []
    code = exec_mod.run_exec(
        prompt, cwd=REPO, skip_git_repo_check=True, stream_deltas=False,
        stdin_cm="", event_sink=sink, **kw,
    )
    assert code == 0
    tid = next(e["thread_id"] for e in sink if e.get("type") == "thread.started")
    return tid


def _pairs(store, tid):
    return [(m["role"], m["content"]) for m in store.load(tid)["messages"]]


def test_single_run_stores_user_and_assistant(tmp_sessions, monkeypatch):
    exec_mod, _ = _patch_provider(monkeypatch, ["first answer"])
    tid = _run(exec_mod, "hello one")
    assert _pairs(tmp_sessions, tid) == [
        ("user", "hello one"),
        ("assistant", "first answer"),
    ]


def test_resume_does_not_duplicate_history(tmp_sessions, monkeypatch):
    exec_mod, _ = _patch_provider(monkeypatch, ["a1", "a2", "a3"])
    tid = _run(exec_mod, "hello one")
    _run(exec_mod, "hello two", resume_thread=tid)
    _run(exec_mod, "hello three", resume_thread=tid)
    pairs = _pairs(tmp_sessions, tid)
    users = [c for r, c in pairs if r == "user"]
    assert users == ["hello one", "hello two", "hello three"]
    assert len(users) == len(set(users))  # no duplicated prompts


def test_resume_keeps_assistant_answers_in_order(tmp_sessions, monkeypatch):
    exec_mod, _ = _patch_provider(monkeypatch, ["a1", "a2"])
    tid = _run(exec_mod, "hello one")
    _run(exec_mod, "hello two", resume_thread=tid)
    assert _pairs(tmp_sessions, tid) == [
        ("user", "hello one"),
        ("assistant", "a1"),
        ("user", "hello two"),
        ("assistant", "a2"),
    ]


def test_resumed_run_sees_prior_turns(tmp_sessions, monkeypatch):
    """The history handed to the provider on resume is the stored transcript."""
    from codemonkey import exec as exec_mod
    from codemonkey.providers.base import ChatTurn

    seen: list = []

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            seen.append([(m["role"], m["content"]) for m in messages])
            return ChatTurn(content="zebra noted", usage={})

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    tid = _run(exec_mod, "remember zebra")
    _run(exec_mod, "what word?", resume_thread=tid)
    assert seen[-1] == [
        ("user", "remember zebra"),
        ("assistant", "zebra noted"),
        ("user", "what word?"),
    ]


def test_schema_retry_stores_pristine_prompt_and_final_answer(
    tmp_sessions, monkeypatch, tmp_path
):
    good = '{"project_name": "codemonkey"}'
    exec_mod, state = _patch_provider(monkeypatch, ['{"project_name": 123}', good])
    schema_file = tmp_path / "s.json"
    schema_file.write_text(json.dumps(SCHEMA))
    tid = _run(exec_mod, "state the project", output_schema=schema_file)
    assert state["n"] == 2  # first answer invalid, one retry
    pairs = _pairs(tmp_sessions, tid)
    assert [r for r, _ in pairs] == ["user", "assistant"]
    assert pairs[0][1] == "state the project"  # no schema scaffolding persisted
    assert "codemonkey" in pairs[1][1]


def test_ephemeral_persists_nothing(tmp_sessions, monkeypatch):
    exec_mod, _ = _patch_provider(monkeypatch, ["x"])
    code = exec_mod.run_exec(
        "hello", cwd=REPO, skip_git_repo_check=True, ephemeral=True,
        stream_deltas=False, stdin_cm="",
    )
    assert code == 0
    assert tmp_sessions.list() == []
