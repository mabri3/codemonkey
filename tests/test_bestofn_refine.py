"""loop48 cycle 113 — the refine pass: losers' bounded evidence seeds ONE
sequential attempt, the SAME machine check decides.

The discriminating claims:

* all candidates fail → the refine fires with the candidates' evidence in its
  prompt (asserted on what the provider RECEIVED: the seed header + per-
  candidate blocks), the refined tree stands, and the run exits 0 when the
  refine verifies;
* candidate 1 passing makes ZERO extra calls even with the flag ON (the
  first-pass fast path is untouched);
* refine also failing keeps the honest failure shape (ok=False, refined=True,
  last_fail_tail) and exits 1;
* `--refine-seeded` without `--best-of N>1` is a usage error, not a silent
  no-op.
"""

from __future__ import annotations

import sys

import pytest

import codemonkey.exec as exec_mod
from codemonkey.bestofn import refine_seed
from codemonkey.exec import ExecUsageError, run_exec


class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


def _write_call(path, content):
    import json as _json
    args = _json.dumps({"path": path, "content": content})
    return 'TOOL_CALL: {"name": "write_file", "arguments": ' + args + '}\n'


class ScriptedProv:
    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.n = 0
        self.seen_user_texts: list[str] = []

    def chat(self, messages, system=None, **kw):
        self.n += 1
        user_joined = "\n".join(str(m.get("content", "")) for m in messages
                                if m.get("role") == "user")
        self.seen_user_texts.append(user_joined)
        if self.n <= len(self.script):
            return Turn(self.script[self.n - 1])
        return Turn("finished")

    def close(self):
        pass


def _run(monkeypatch, tmp_path, prov, **kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    monkeypatch.setattr(exec_mod, "_provider_from_config", patched)
    events: list = []
    params = dict(
        cwd=tmp_path, skip_git_repo_check=True, ephemeral=True,
        stream_deltas=False, stdin_cm="", sandbox="workspace-write",
        approval="never", event_sink=events,
    )
    params.update(kw)
    code = run_exec("write the answer file", **params)
    return code, events


def _verifier(target="RIGHT"):
    py = sys.executable
    return (f'"{py}" -c "import sys; sys.exit(0 if '
            f"open('answer.txt').read().strip()=={target!r} else 1)\"")


def _types(events, etype):
    return [e for e in events if e.get("type") == etype]


def test_refine_fires_when_all_candidates_fail_and_seed_is_received(monkeypatch, tmp_path):
    prov = ScriptedProv([
        _write_call("answer.txt", "WRONG1"), "attempt one done",
        _write_call("answer.txt", "WRONG2"), "attempt two done",
        _write_call("answer.txt", "RIGHT"), "refined done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov,
                        best_of=2, verify_command=_verifier(),
                        refine_seeded=True)
    assert code == 0
    assert (tmp_path / "answer.txt").read_text() == "RIGHT"
    ref = _types(events, "bestofn.refine")
    assert len(ref) == 1
    assert ref[0]["candidates"] == 2 and ref[0]["refined"] == 1
    assert ref[0]["verified"] is True
    done = _types(events, "bestofn.completed")
    assert len(done) == 1 and done[0]["ok"] is True and done[0].get("refined") is True
    # the refine turn RECEIVED the bounded failure evidence: header +
    # both candidates' blocks (the information first-pass-wins discarded)
    refine_prompt = prov.seen_user_texts[4]  # 5th call = first refine turn
    assert "failed its machine check" in refine_prompt
    assert "[candidate 1]" in refine_prompt and "[candidate 2]" in refine_prompt


def test_candidate_one_pass_makes_zero_extra_calls_even_with_flag_on(monkeypatch, tmp_path):
    prov = ScriptedProv([
        _write_call("answer.txt", "RIGHT"), "attempt one done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov,
                        best_of=2, verify_command=_verifier(),
                        refine_seeded=True)
    assert code == 0
    assert prov.n == 2                     # exactly attempt 1; no refine call
    assert _types(events, "bestofn.refine") == []
    done = _types(events, "bestofn.completed")
    assert len(done) == 1 and done[0]["ok"] is True and "refined" not in done[0]


def test_refine_failing_stays_honest(monkeypatch, tmp_path):
    prov = ScriptedProv([
        _write_call("answer.txt", "W1"), "one",
        _write_call("answer.txt", "W2"), "two",
        _write_call("answer.txt", "W3"), "refined but still wrong",
    ])
    code, events = _run(monkeypatch, tmp_path, prov,
                        best_of=2, verify_command=_verifier(),
                        refine_seeded=True)
    assert code == 1
    assert (tmp_path / "answer.txt").read_text() == "W3"  # refined tree stands
    ref = _types(events, "bestofn.refine")
    assert len(ref) == 1 and ref[0]["verified"] is False
    done = _types(events, "bestofn.completed")
    assert len(done) == 1
    assert done[0]["ok"] is False and done[0].get("refined") is True
    assert "last_fail_tail" in done[0]


def test_flag_without_best_of_is_usage_error(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(ExecUsageError, match="refine-seeded"):
        run_exec("whatever", cwd=tmp_path, skip_git_repo_check=True,
                 ephemeral=True, stream_deltas=False, stdin_cm="",
                 refine_seeded=True)


def test_refine_seed_is_bounded_and_marked():
    one = refine_seed([{"index": 0, "tail": "x" * 500, "text": "y" * 400}])
    assert "[candidate 1]" in one and "seed truncated" not in one
    big = refine_seed([{"index": i, "tail": "t" * 400, "text": "u" * 300}
                       for i in range(20)])
    assert "seed truncated" in big
    assert len(big) < 4100  # cap + marker, never unbounded
    assert refine_seed([{"index": 0, "tail": "", "text": ""}]).count("(no tail)") == 1


def test_cli_surface_refine_flag_reaches_run_exec():
    """CLI pin (flags BEFORE the positional — the exec group's variadic
    prompt swallows trailing flags, an order property shared by EVERY exec
    flag): `--refine-seeded` with no --best-of exits 2 with the reason."""
    from typer.testing import CliRunner

    from codemonkey.cli import app

    r = CliRunner().invoke(app, ["exec", "--refine-seeded",
                                 "--skip-git-repo-check", "x"])
    assert r.exit_code == 2
    assert "refine-seeded" in (r.output or "")
