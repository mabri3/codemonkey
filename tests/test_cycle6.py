"""Cycle 6 unit tests: structured output validation + sessions/resume.

No network — schema.py is pure, sessions.py writes to a tmp sessions dir,
and the CLI-level tests patch the provider with the same FakeProvider used
by test_exec.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


# -- schema.py ------------------------------------------------------------

SCHEMA = {
    "type": "object",
    "properties": {
        "project_name": {"type": "string"},
        "programming_languages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["project_name", "programming_languages"],
}


def test_load_schema_file_ok(tmp_path):
    from codemonkey import schema as sm

    p = tmp_path / "s.json"
    p.write_text(json.dumps(SCHEMA))
    out = sm.load_schema_file(p)
    assert out["type"] == "object"


def test_load_schema_file_missing(tmp_path):
    from codemonkey import schema as sm

    with pytest.raises(sm.SchemaError):
        sm.load_schema_file(tmp_path / "nope.json")


def test_load_schema_file_invalid_json(tmp_path):
    from codemonkey import schema as sm

    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(sm.SchemaError):
        sm.load_schema_file(p)


def test_extract_json_plain():
    from codemonkey import schema as sm

    assert sm.extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_fenced():
    from codemonkey import schema as sm

    text = 'Here you go:\n```json\n{"a": 2}\n```\nthanks'
    assert sm.extract_json(text) == {"a": 2}


def test_extract_json_embedded():
    from codemonkey import schema as sm

    text = 'answer: {"b": 3} some trailing words'
    assert sm.extract_json(text) == {"b": 3}


def test_extract_json_none():
    from codemonkey import schema as sm

    assert sm.extract_json("no json here") is None


def test_validate_ok():
    from codemonkey import schema as sm

    ok, errs = sm.validate({"project_name": "codemonkey", "programming_languages": ["python"]}, SCHEMA)
    assert ok, errs


def test_validate_missing_required():
    from codemonkey import schema as sm

    ok, errs = sm.validate({"project_name": "x"}, SCHEMA)
    assert not ok
    assert "programming_languages" in errs


def test_validate_wrong_type():
    from codemonkey import schema as sm

    ok, errs = sm.validate({"project_name": 7, "programming_languages": []}, SCHEMA)
    assert not ok


# -- sessions.py ----------------------------------------------------------

@pytest.fixture()
def tmp_sessions(monkeypatch, tmp_path):
    """Redirect the sessions dir to a tmp path and bind the module-level
    `store` accessor at a tmp-dir-backed instance (exec.py reads
    sessions_mod.store(cfg))."""
    from codemonkey import sessions as sess

    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    monkeypatch.setattr(sess, "sessions_dir", lambda: sess_dir)
    inst = sess.SessionStore()
    monkeypatch.setattr(sess, "store", lambda cfg=None, _i=inst: _i)
    return inst


def test_session_roundtrip(tmp_sessions):
    tid = "t_abc123"
    tmp_sessions.append_meta(tid, provider="local", model="m", cwd="/x")
    tmp_sessions.append_message(tid, "user", "Remember the token word: zebra.")
    tmp_sessions.append_message(tid, "assistant", "ok")

    data = tmp_sessions.load(tid)
    assert data["meta"]["thread_id"] == tid
    assert data["meta"]["provider"] == "local"
    assert data["messages"] == [
        {"role": "user", "content": "Remember the token word: zebra."},
        {"role": "assistant", "content": "ok"},
    ]


def test_session_load_missing(tmp_sessions):
    with pytest.raises(FileNotFoundError):
        tmp_sessions.load("t_missing")


def test_session_list_and_latest(tmp_sessions):
    for tid in ("t_one", "t_two"):
        tmp_sessions.append_meta(tid, provider="local", model="m", cwd="/x")
        tmp_sessions.append_message(tid, "user", f"prompt from {tid}")

    items = tmp_sessions.list()
    ids = [i["thread_id"] for i in items]
    assert ids == ["t_two", "t_one"]  # newest mtime first
    assert items[0]["first_prompt"].startswith("prompt from t_two")
    assert tmp_sessions.latest() == "t_two"


def _fp_fixture(monkeypatch):
    """Patch exec._provider_from_config to return a fresh-typed fake provider."""
    from codemonkey import exec as exec_mod

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            from codemonkey.providers.base import ChatTurn

            return ChatTurn(content="pong", usage={})

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    return exec_mod


def test_exec_persists_session(tmp_sessions, monkeypatch):
    """run_exec writes meta+messages for the new thread id."""
    exec_mod = _fp_fixture(monkeypatch)
    code = exec_mod.run_exec(
        "ping",
        cwd=REPO,
        skip_git_repo_check=True,
        stream_deltas=False,
        stdin_cm="",
    )
    assert code == 0

    items = tmp_sessions.list()
    assert len(items) == 1
    assert "ping" in items[0]["first_prompt"]


def test_exec_ephemeral_skips_persistence(tmp_sessions, monkeypatch):
    exec_mod = _fp_fixture(monkeypatch)

    code = exec_mod.run_exec(
        "ping", cwd=REPO, skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="",
    )
    assert code == 0
    assert tmp_sessions.list() == []


def test_exec_schema_validation_ok(tmp_sessions, monkeypatch, tmp_path):
    from codemonkey import exec as exec_mod
    from codemonkey import schema as sm

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            from codemonkey.providers.base import ChatTurn

            # Verify schema instructions were appended
            assert "JSON Schema" in messages[-1]["content"]
            return ChatTurn(
                content='{"project_name": "codemonkey", "programming_languages": ["python"]}',
                usage={},
            )

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    schema_file = tmp_path / "s.json"
    schema_file.write_text(json.dumps(SCHEMA))
    code = exec_mod.run_exec(
        "state the project",
        cwd=REPO,
        skip_git_repo_check=True,
        ephemeral=True,
        stream_deltas=False,
        output_schema=schema_file,
        stdin_cm="",
    )
    assert code == 0


def test_exec_schema_validation_retry(tmp_sessions, monkeypatch, tmp_path):
    """First answer invalid -> one retry turn triggered, retry passes."""
    from codemonkey import exec as exec_mod

    calls = {"n": 0}

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            from codemonkey.providers.base import ChatTurn

            calls["n"] += 1
            if calls["n"] == 1:
                return ChatTurn(content='{"project_name": 123}', usage={})
            # retry turn: the retry prompt (with validation errors) must be present
            debrief = messages[-1]["content"]
            assert "failed JSON Schema validation" in debrief
            return ChatTurn(
                content='{"project_name": "codemonkey", "programming_languages": ["python"]}',
                usage={},
            )

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    schema_file = tmp_path / "s.json"
    schema_file.write_text(json.dumps(SCHEMA))
    code = exec_mod.run_exec(
        "state the project",
        cwd=REPO,
        skip_git_repo_check=True,
        ephemeral=True,
        stream_deltas=False,
        output_schema=schema_file,
        stdin_cm="",
    )
    assert code == 0
    assert calls["n"] == 2


def test_exec_schema_validation_fail_exits_1(tmp_sessions, monkeypatch, tmp_path):
    from codemonkey import exec as exec_mod

    class FP:
        protocol = "openai"
        model = "fake"

        def chat(self, messages, **kw):
            from codemonkey.providers.base import ChatTurn

            return ChatTurn(content="no json at all", usage={})

        def close(self):
            pass

    monkeypatch.setattr(
        exec_mod, "_provider_from_config", lambda cfg, name, model: ("local", FP())
    )
    schema_file = tmp_path / "s.json"
    schema_file.write_text(json.dumps(SCHEMA))
    code = exec_mod.run_exec(
        "state the project",
        cwd=REPO,
        skip_git_repo_check=True,
        ephemeral=True,
        stream_deltas=False,
        output_schema=schema_file,
        stdin_cm="",
    )
    assert code == 1
