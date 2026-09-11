"""loop48 cycle 114 — the tournament selector: tier-2 selection, injected and
machine-checked, honest when it cannot decide.

Claims pinned here:

* DETERMINISM: a strict total-order comparison selects the same winner under
  any input permutation; ties break to the lower index;
* HONESTY: no comparison function → selected None with the reason (never a
  guess); a malformed verdict or a raising comparison REFUSES the whole
  selection naming the offending pair;
* the exec-level runs: `--best-of 2 --tournament-compare <cmd>` (no verify
  command) selects the candidate the command picks, restores THAT
  candidate's tree, exits 0, and puts `bestofn.tournament` + `via: tournament`
  on the trace; a malformed command refuses and the LAST tree stays (exit 1).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import codemonkey.exec as exec_mod
from codemonkey.bestofn import (run_compare_cmd, select_by_tournament)
from codemonkey.exec import ExecUsageError, run_exec


# ---------------- the pure selector ----------------

def _strict_cmp(rank):
    def cmp(a, b):
        ra, rb = rank[a], rank[b]
        return "a" if ra > rb else ("b" if rb > ra else "equal")
    return cmp


def test_strict_total_order_wins_under_any_permutation():
    cands = [{"text": "alpha"}, {"text": "beta"}, {"text": "gamma"}]
    rank = {"alpha": 3, "beta": 1, "gamma": 2}
    for order in ([0, 1, 2], [2, 1, 0], [1, 2, 0], [2, 0, 1]):
        shuffled = [cands[i] for i in order]
        sel = select_by_tournament(shuffled, compare_fn=_strict_cmp(rank))
        assert shuffled[sel["selected"]]["text"] == "alpha"


def test_ties_break_to_the_lower_index():
    sel = select_by_tournament(
        [{"text": "one"}, {"text": "two"}],
        compare_fn=lambda a, b: "equal")
    assert sel["selected"] == 0 and sel["wins"] == [0, 0]


def test_no_comparison_is_the_honest_empty():
    sel = select_by_tournament([{"text": "x"}, {"text": "y"}])
    assert sel["selected"] is None and "no comparison provided" in sel["reason"]


def test_malformed_verdict_refuses_naming_the_pair():
    sel = select_by_tournament(
        [{"text": "x"}, {"text": "y"}],
        compare_fn=lambda a, b: "maybe")
    assert sel["selected"] is None
    assert "malformed verdict at (0,1)" in sel["reason"] and "'maybe'" in sel["reason"]


def test_raising_comparison_refuses():
    def boom(a, b):
        raise RuntimeError("nope")
    sel = select_by_tournament([{"text": "x"}, {"text": "y"}], compare_fn=boom)
    assert sel["selected"] is None and "RuntimeError" in sel["reason"]


def test_run_compare_cmd_reads_the_first_stdout_line(tmp_path):
    (tmp_path / "cmp.sh").write_text(
        'if grep -q two "$1"; then echo a; '
        'elif grep -q two "$2"; then echo b; else echo equal; fi\n')
    cmd = f"bash {tmp_path}/cmp.sh"
    assert run_compare_cmd(cmd, "attempt one", "attempt two", tmp_path) == "b"
    assert run_compare_cmd(cmd, "attempt two", "attempt one", tmp_path) == "a"
    assert run_compare_cmd(cmd, "neither", "neither", tmp_path) == "equal"
    # malformed output is returned AS-IS for the selector to refuse
    (tmp_path / "bad.sh").write_text("echo maybe\n")
    assert run_compare_cmd(f"bash {tmp_path}/bad.sh", "a", "b", tmp_path) == "maybe"
    # a crashing command is a reason string, not a verdict
    (tmp_path / "crash.sh").write_text("exit 3\n")
    out = run_compare_cmd(f"bash {tmp_path}/crash.sh", "a", "b", tmp_path)
    assert out.startswith("comparison command exit 3")


# ---------------- the exec-level path ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
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


def _run(monkeypatch, tmp_path, prov, **kw):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    monkeypatch.delenv("CODEMONKEY_VERIFY_COMMAND", raising=False)
    # HOME is the tmp dir: no user config, so no config verify_command can
    # leak into the "no machine verifier" premise of these tests
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


def _types(events, etype):
    return [e for e in events if e.get("type") == etype]


def test_exec_tournament_selects_the_command_pick_and_restores_its_tree(tmp_path, monkeypatch):
    cmp = tmp_path / "cmp.sh"
    cmp.write_text('if grep -q two "$1"; then echo a; '
                   'elif grep -q two "$2"; then echo b; else echo equal; fi\n')
    prov = ScriptedProv([
        _write_call("answer.txt", "ONE"), "attempt one done",
        _write_call("answer.txt", "TWO"), "attempt two done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov, best_of=2,
                        tournament_compare=f"bash {cmp}")
    assert code == 0
    assert (tmp_path / "answer.txt").read_text() == "TWO"  # winner's tree
    tour = _types(events, "bestofn.tournament")
    assert len(tour) == 1 and tour[0]["selected"] == 1
    done = _types(events, "bestofn.completed")
    assert done[0]["ok"] is True and done[0]["via"] == "tournament"
    assert done[0]["index"] == 1


def test_exec_tournament_malformed_command_refuses_and_keeps_last_tree(tmp_path, monkeypatch):
    bad = tmp_path / "bad.sh"
    bad.write_text("echo maybe\n")
    prov = ScriptedProv([
        _write_call("answer.txt", "ONE"), "attempt one done",
        _write_call("answer.txt", "TWO"), "attempt two done",
    ])
    code, events = _run(monkeypatch, tmp_path, prov, best_of=2,
                        tournament_compare=f"bash {bad}")
    assert code == 1
    assert (tmp_path / "answer.txt").read_text() == "TWO"  # last tree KEPT
    done = _types(events, "bestofn.completed")
    assert done[0]["ok"] is False and done[0]["via"] == "tournament"
    assert "malformed verdict" in done[0]["last_fail_tail"]


def test_usage_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(ExecUsageError, match="tournament needs"):
        run_exec("x", cwd=tmp_path, skip_git_repo_check=True, ephemeral=True,
                 stream_deltas=False, stdin_cm="", tournament_compare="true")
    with pytest.raises(ExecUsageError, match="mutually exclusive"):
        run_exec("x", cwd=tmp_path, skip_git_repo_check=True, ephemeral=True,
                 stream_deltas=False, stdin_cm="", best_of=2,
                 verify_command="true", tournament_compare="true")


def test_verify_less_bestof_still_usage_error_without_selector(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    with pytest.raises(ExecUsageError, match="verify command"):
        run_exec("x", cwd=tmp_path, skip_git_repo_check=True, ephemeral=True,
                 stream_deltas=False, stdin_cm="", best_of=2)
