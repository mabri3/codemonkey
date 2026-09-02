"""Cycle 5 unit tests: exec core against a FAKE provider (no network).

Live probes (pong / --json / stdin) run as the cycle verify against the real
llama.cpp server; here we lock the stdout-purity contract, event ordering,
stdin handling, the git guard, and the run-error paths deterministically.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from codemonkey.providers.base import ChatTurn, ProviderError

REPO = Path(__file__).resolve().parent.parent
PONG = "Reply with exactly the word pong and nothing else."


class FakeProvider:
    """One-turn provider: returns a canned final answer, no tool calls."""

    protocol = "openai"

    def __init__(self, text: str = "pong"):
        self.text = text
        self.closed = False

    def chat(self, messages, **kw):
        return ChatTurn(content=self.text, usage={"prompt_tokens": 5, "completion_tokens": 1})

    def list_models(self):
        return ["fake-model"]

    def close(self):
        self.closed = True


class FailProvider(FakeProvider):
    def chat(self, messages, **kw):
        raise ProviderError("boom from server", status=503)


def run_cli(args, cwd=None, stdin_text=None, env_provider=None):
    """Run the CLI in-process via CliRunner with a patched provider."""
    from typer.testing import CliRunner
    from codemonkey import cli
    import codemonkey.exec as exec_mod

    runner = CliRunner()
    if env_provider is not None:
        orig = exec_mod._provider_from_config

        def patched(cfg, provider_name, model):
            name, _ = orig(cfg, provider_name, model)
            return name, env_provider

        exec_mod._provider_from_config = patched
        try:
            result = runner.invoke(cli.app, args, input=stdin_text)
        finally:
            exec_mod._provider_from_config = orig
    else:
        result = runner.invoke(cli.app, args, input=stdin_text)
    return result


# --------------------------------------------------------------------------
# text mode: stdout purity
# --------------------------------------------------------------------------

def test_exec_text_stdout_is_final_only():
    r = run_cli(["exec", "--skip-git-repo-check", PONG], env_provider=FakeProvider("pong"))
    assert r.exit_code == 0, r.stderr
    assert r.stdout.strip() == "pong"
    # stdout must contain nothing but the final message
    assert "thread" not in r.stdout and "turn" not in r.stdout


def test_exec_json_every_line_parses_with_markers():
    r = run_cli(
        ["exec", "--skip-git-repo-check", "--json", PONG], env_provider=FakeProvider("pong")
    )
    assert r.exit_code == 0, r.stderr
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert lines, "expected JSONL output"
    events = [json.loads(l) for l in lines]  # raises if any line isn't JSON
    types = [e.get("type") for e in events]
    assert "thread.started" in types
    assert "turn.started" in types
    assert "turn.completed" in types
    assert types.index("thread.started") == 0  # first line


def test_exec_json_thread_started_has_thread_id():
    r = run_cli(
        ["exec", "--skip-git-repo-check", "--json", PONG], env_provider=FakeProvider("pong")
    )
    first = json.loads(r.stdout.splitlines()[0])
    assert first["type"] == "thread.started"
    assert first["thread_id"]


# --------------------------------------------------------------------------
# stdin handling
# --------------------------------------------------------------------------

def test_exec_dash_reads_stdin_as_prompt():
    seen = {}

    class Spy(FakeProvider):
        def chat(self, messages, **kw):
            seen["prompt"] = messages[0]["content"]
            return super().chat(messages, **kw)

    r = run_cli(
        ["exec", "--skip-git-repo-check", "-"],
        stdin_text="Reply with exactly: banana",
        env_provider=Spy("banana"),
    )
    assert r.exit_code == 0, r.stderr
    assert r.stdout.strip() == "banana"
    assert "banana" in seen["prompt"]


def test_exec_piped_stdin_plus_arg_appends_context():
    seen = {}

    class Spy(FakeProvider):
        def chat(self, messages, **kw):
            seen["prompt"] = messages[0]["content"]
            return super().chat(messages, **kw)

    r = run_cli(
        ["exec", "--skip-git-repo-check", "the question"],
        stdin_text="some context",
        env_provider=Spy("ok"),
    )
    assert r.exit_code == 0, r.stderr
    assert "some context" in seen["prompt"]
    assert "the question" in seen["prompt"]
    assert seen["prompt"].index("some context") < seen["prompt"].index("the question")


def test_exec_no_prompt_is_usage_error():
    r = run_cli(["exec", "--skip-git-repo-check"], env_provider=FakeProvider())
    assert r.exit_code == 2
    assert "prompt" in r.stderr.lower()


# --------------------------------------------------------------------------
# git guard
# --------------------------------------------------------------------------

def test_git_guard_outside_repo_exits_2(tmp_path):
    r = run_cli(["exec", "-C", str(tmp_path), "hi"], env_provider=FakeProvider("x"))
    assert r.exit_code == 2
    assert "git repository" in r.stderr
    assert "--skip-git-repo-check" in r.stderr


def test_git_guard_inside_repo_ok(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    r = run_cli(["exec", "-C", str(tmp_path), "hi"], env_provider=FakeProvider("hi"))
    assert r.exit_code == 0, r.stderr
    assert r.stdout.strip() == "hi"


def test_find_git_root_walks_up(tmp_path):
    (tmp_path / ".git").mkdir()
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    from codemonkey.exec import find_git_root

    assert find_git_root(deep) == tmp_path


# --------------------------------------------------------------------------
# output-last-message / exit codes
# --------------------------------------------------------------------------

def test_output_last_message_tee(tmp_path):
    out = tmp_path / "last.txt"
    r = run_cli(
        ["exec", "--skip-git-repo-check", "-o", str(out), PONG],
        env_provider=FakeProvider("pong\n\nsome\nmulti-line\nanswer"),
    )
    assert r.exit_code == 0, r.stderr
    assert out.read_text().startswith("pong")
    assert "multi-line" in out.read_text()


def test_run_error_exits_1():
    r = run_cli(
        ["exec", "--skip-git-repo-check", "hi"], env_provider=FailProvider()
    )
    assert r.exit_code == 1
    assert "boom" in r.stderr
    # stdout purity still holds on error
    assert r.stdout.strip() == ""


def test_output_schema_flag_is_usage_error_until_cycle6():
    r = run_cli(
        ["exec", "--skip-git-repo-check", "--output-schema", "x.json", "hi"],
        env_provider=FakeProvider("x"),
    )
    assert r.exit_code == 2
    assert "output-schema" in r.stderr
