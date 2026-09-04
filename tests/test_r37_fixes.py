"""R37F1–R37F5 regression tests (closing-critic fix cycle).

Each test fails on the pre-fix code with the exact defect named in
`build/critic-r37.md`:

  R37F1 loop.py:356    UnboundLocalError on any journaled run whose tool call
                       matches a permission rule (the whole enforcement path).
  R37F2 rules_cli.py   `codemonkey rules-compile` -> NameError: 'cfg'.
  R37F3 schema.py      invalid --output-schema -> NameError instead of the
                       SchemaError that maps to exit 2.
  R37F4 adaptivemem    duplicate memory lines re-emitted past the budget and
                       reported as kept AND dropped.
  R37F5 protocol.py    `Optional` annotation with no import.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from codemonkey.adaptivemem import adaptive_select
from codemonkey.journal import read_thread
from codemonkey.loop import run_turns
from codemonkey.sandbox import ToolContext
from codemonkey.schema import SchemaError, load_schema_file


class _Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class _Prov:
    protocol = "openai"

    def __init__(self, calls):
        self.calls = list(calls)
        self.n = 0

    def chat(self, messages, system=None, tools=None, stream=False,
             on_token=None, cache_prompt=True, **kw):
        self.n += 1
        if self.n <= len(self.calls):
            return _Turn(self.calls[self.n - 1])
        return _Turn("finished")


@pytest.fixture()
def jhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


_WRITE_CALL = ('TOOL_CALL: {"name": "write_file", '
               '"arguments": {"path": "a.txt", "content": "x"}}\n')


def _run(tmp_path, rules):
    return run_turns(_Prov([_WRITE_CALL]), "go",
                     ToolContext(workdir=tmp_path, sandbox="workspace-write",
                                 timeout=10),
                     tool_protocol="prompt", max_turns=3,
                     journal_thread="tid", perm_rules=rules)


def test_r37f1_deny_rule_on_journaled_run_does_not_crash(tmp_path, jhome):
    turn = _run(tmp_path, [{"tool": "write_file", "action": "deny"}])
    assert turn.content == "finished"
    assert not (tmp_path / "a.txt").exists(), "deny rule must block the write"


def test_r37f1_rule_hit_is_journaled_with_a_real_key(tmp_path, jhome):
    _run(tmp_path, [{"tool": "write_file", "action": "deny"}])
    rule_recs = [r for r in read_thread("tid")
                 if str(r.get("status", "")).startswith("rule-")]
    assert rule_recs, "the rule decision must reach the journal audit trail"
    key = rule_recs[0].get("key", "")
    assert key.endswith(":rule")
    assert key != ":rule", "the audit record needs the real action key prefix"


def test_r37f1_allow_rule_still_executes(tmp_path, jhome):
    turn = _run(tmp_path, [{"tool": "write_file", "action": "allow"}])
    assert turn.content == "finished"
    assert (tmp_path / "a.txt").read_text() == "x"


def test_r37f2_rules_compile_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    from codemonkey.cli import app

    result = CliRunner().invoke(app, ["rules-compile"])
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output


def test_r37f3_invalid_schema_raises_schema_error(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"type": "not-a-type"}))
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_r37f4_duplicate_lines_respect_the_budget():
    out, dropped = adaptive_select(["a b c", "a b c", "x"], token_budget=3)
    assert len(out.split()) <= 3
    assert out.split("\n") == ["a b c"]
    # the second occurrence and the unaffordable line are dropped, and the
    # duplicate is emitted exactly once (pre-fix: emitted twice, 6 tokens)
    assert dropped == ["a b c", "x"]


def test_r37f4_duplicates_kept_when_budget_allows():
    out, dropped = adaptive_select(["a b c", "a b c", "x"], token_budget=7)
    assert out.split("\n") == ["a b c", "a b c", "x"]
    assert dropped == []


def test_r37f5_protocol_annotations_resolve():
    import typing

    from codemonkey import protocol

    hints = typing.get_type_hints(protocol._extract_json_object)
    assert hints["return"] == typing.Optional[str]
