"""loop48 cycle 115 — the cost gate: the projected spend is printed BEFORE it
is incurred, and a declared token budget is enforced at the same boundary so
the crossing provider call never happens.

The discriminating claims:

* a tiny declared budget refuses at the candidate boundary — exit 4,
  `budget.exhausted {stage: "bestofn-boundary"}`, a resumable job, and the
  PROVIDER-CALL COUNT proves candidate 2 never started (the boundary check,
  not a post-hoc report);
* the projection line prints before candidate 2 and names the declared
  limit, the estimate and the spend so far;
* a budget that fits → the line prints and the run proceeds to the verify
  pass;
* `--best-of 1` prints nothing new (no gate line at all);
* the tournament path is gated identically, and the refine is gated too.
"""

from __future__ import annotations

import sys

import codemonkey.exec as exec_mod
from codemonkey.exec import run_exec


class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}   # each chat turn costs 10
        self.tool_calls = []


def _write_call(path, content):
    import json as _json
    return ('TOOL_CALL: {"name": "write_file", "arguments": '
            + _json.dumps({"path": path, "content": content}) + '}\n')


class ScriptedProv:
    protocol = "openai"

    def __init__(self, script):
        self.script = list(script)
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        return Turn(self.script[self.n - 1] if self.n <= len(self.script)
                    else "finished")

    def close(self):
        pass


def _run(monkeypatch, tmp_path, prov, budget_tokens=None, **kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    monkeypatch.delenv("CODEMONKEY_VERIFY_COMMAND", raising=False)
    if budget_tokens is None:
        monkeypatch.delenv("CODEMONKEY_BUDGET_TOKENS", raising=False)
    else:
        monkeypatch.setenv("CODEMONKEY_BUDGET_TOKENS", str(budget_tokens))
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


def test_boundary_refuses_before_the_crossing_call(monkeypatch, tmp_path, capsys):
    """Candidate 1 spends 20 (2 turns × 10). Averaging 20 per candidate, the
    next one would cross a 25-token budget → refused BEFORE its first call."""
    prov = ScriptedProv([
        _write_call("answer.txt", "WRONG1"), "one",
        _write_call("answer.txt", "WRONG2"), "two",
        _write_call("answer.txt", "RIGHT"), "three",
    ])
    code, events = _run(monkeypatch, tmp_path, prov, budget_tokens=25,
                        best_of=3, verify_command=_verifier())
    err = capsys.readouterr().err
    assert code == 4
    assert prov.n == 2                      # ONLY candidate 1's two turns ran
    assert (tmp_path / "answer.txt").read_text() == "WRONG1"  # tree kept
    bex = _types(events, "budget.exhausted")
    assert len(bex) == 1 and bex[0]["stage"] == "bestofn-boundary"
    assert bex[0]["limit"] == 25 and bex[0]["observed"] == 20
    done = _types(events, "bestofn.completed")
    assert done and done[0]["via"] == "budget-refusal"
    assert "projected extra spend" in err and "declared tokens=25" in err
    assert "refused before the provider call" in err
    assert "resumable job: job-" in err      # a REAL id, not "None"


def test_projection_prints_and_run_proceeds_when_budget_fits(monkeypatch, tmp_path, capsys):
    prov = ScriptedProv([
        _write_call("answer.txt", "WRONG"), "one",
        _write_call("answer.txt", "RIGHT"), "two",
    ])
    code, events = _run(monkeypatch, tmp_path, prov, budget_tokens=1000,
                        best_of=2, verify_command=_verifier())
    err = capsys.readouterr().err
    assert code == 0
    assert (tmp_path / "answer.txt").read_text() == "RIGHT"
    assert "projected extra spend: 1 more candidate(s)" in err
    assert "declared tokens=1000" in err
    assert "spent so far=20" in err
    assert _types(events, "bestofn.completed")[0]["ok"] is True


def test_best_of_one_prints_no_gate_line(monkeypatch, tmp_path, capsys):
    prov = ScriptedProv([_write_call("answer.txt", "solo"), "done"])
    code, _ = _run(monkeypatch, tmp_path, prov, budget_tokens=1000)
    err = capsys.readouterr().err
    assert code == 0
    assert "[bestofn]" not in err


def test_tournament_path_is_gated_identically(monkeypatch, tmp_path, capsys):
    cmp = tmp_path / "cmp.sh"
    cmp.write_text("echo a\n")
    prov = ScriptedProv([
        _write_call("answer.txt", "ONE"), "attempt one done",
        _write_call("answer.txt", "TWO"), "attempt two done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov, budget_tokens=25,
                        best_of=2, tournament_compare=f"bash {cmp}")
    assert code == 4
    assert prov.n == 2                      # candidate 2 never started
    assert _types(events, "bestofn.tournament") == []
    assert _types(events, "budget.exhausted")[0]["stage"] == "bestofn-boundary"


def test_refine_is_gated_too(monkeypatch, tmp_path, capsys):
    """Both candidates fit (20+20=40 ≤ 50), but the refine's crossing is
    refused at its own boundary — no refine call starts."""
    prov = ScriptedProv([
        _write_call("answer.txt", "W1"), "one",
        _write_call("answer.txt", "W2"), "two",
        _write_call("answer.txt", "RIGHT"), "refine",
    ])
    code, events = _run(monkeypatch, tmp_path, prov, budget_tokens=50,
                        best_of=2, verify_command=_verifier(),
                        refine_seeded=True)
    err = capsys.readouterr().err
    assert code == 4
    assert prov.n == 4                      # 2 candidates × 2 turns; no refine
    assert _types(events, "bestofn.refine") == []
    assert "projection" not in err.lower() or "projected extra spend: 1 more" in err
    assert (tmp_path / "answer.txt").read_text() == "W2"
