"""Cycle 88 (loop 39): failure taxonomy over journal records.

R-I entry-point probe: scripted failing real-exec run (fake provider,
repeated denied writes) → `codemonkey journal show <thread>` prints the
taxonomy category rows with counts.
"""

from __future__ import annotations

from typer.testing import CliRunner

from codemonkey.cli import app
from codemonkey.failclass import UNMAPPED, classify_record, summarize_taxonomy

runner = CliRunner()


def _rec(**kw):
    base = {"type": "outcome", "tool": "shell", "key": "k",
            "status": "error", "error_class": "tool-error", "output": ""}
    base.update(kw)
    return base


# ---------------- mapping ----------------

def test_auth_maps_to_constraint():
    cat, _ = classify_record(_rec(error_class="auth"))
    assert cat == "constraint-violation"


def test_schema_mismatch_maps_to_wrong_argument():
    cat, _ = classify_record(_rec(error_class="schema_mismatch"))
    assert cat == "wrong-argument"


def test_parse_maps_to_observation_failure():
    cat, _ = classify_record(_rec(error_class="parse"))
    assert cat == "observation-failure"


def test_denied_output_maps_to_constraint():
    cat, _ = classify_record(_rec(tool="write_file", output="error: denied by permission rule"))
    assert cat == "constraint-violation"


def test_missing_command_maps_to_wrong_tool():
    cat, _ = classify_record(_rec(tool="shell", output="bash: frobnicate: command not found"))
    assert cat == "wrong-tool"


def test_bad_anchor_maps_to_wrong_argument():
    cat, _ = classify_record(_rec(tool="edit_file", output="anchor did not match"))
    assert cat == "wrong-argument"


def test_transient_infrastructure_stays_unmapped():
    for cls in ("timeout", "transport"):
        cat, reason = classify_record(_rec(error_class=cls))
        assert cat == UNMAPPED and reason == "transient-infrastructure"


def test_ok_and_empty_are_no_failure():
    assert classify_record(_rec(error_class="ok"))[0] == UNMAPPED
    assert classify_record(_rec(error_class=""))[0] == UNMAPPED


def test_unknown_class_is_honest():
    cat, reason = classify_record(_rec(error_class="mystery"))
    assert cat == UNMAPPED and reason.startswith("uncoded-class")


def test_summarize_counts_failures_only():
    recs = [_rec(error_class="auth"), _rec(error_class="auth"),
            _rec(error_class="timeout"), _rec(error_class="ok"),
            _rec(error_class="")]
    counts = summarize_taxonomy(recs)
    assert counts == {"constraint-violation": 2, UNMAPPED: 1}


# ---------------- R-I: scripted failing run → journal show ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 1}
        self.tool_calls = []


class DeniedProv:
    """Every turn: attempt the disallowed write, then give up the turn."""
    protocol = "openai"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n % 2 == 1:
            return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                        '{"path": "/tmp/cm88-denied.txt", "content": "x"}}\n')
        return Turn("blocked, stopping")

    def close(self):
        pass


def test_failing_run_surfaces_taxonomy_in_journal_show(tmp_path, monkeypatch):
    import codemonkey.exec as exec_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    prov = DeniedProv()
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    code = exec_mod.run_exec(
        "Write x to /tmp/cm88-denied.txt", cwd=tmp_path,
        skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="", sandbox="workspace-write", approval="never",
        event_sink=events, max_turns=4)
    assert code in (0, 1)
    tids = [e.get("thread_id") for e in events
            if e.get("type") == "thread.started" and e.get("thread_id")]
    assert tids, "run must have started a thread"
    r = runner.invoke(app, ["journal", "show", tids[0]])
    assert r.exit_code == 0, r.output
    assert "-- failure taxonomy --" in r.output
    assert "constraint-violation" in r.output
