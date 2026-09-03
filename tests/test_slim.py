"""Cycle 35 (loop8): tool-output slimming."""

from __future__ import annotations

from codemonkey.slim import slim


def test_blank_line_collapse():
    out = "a\n\n\n\n\nb\n" + "x" * 300
    slimmed, stats = slim(out)
    assert "\n\n\n" not in slimmed
    assert stats["applied"] and stats["chars_saved"] > 0


def test_ansi_strip():
    out = "\x1b[31mred\x1b[0m plain " + "y" * 300
    slimmed, stats = slim(out)
    assert "\x1b[" not in slimmed
    assert "red" in slimmed and "plain" in slimmed
    assert stats["applied"]


def test_trailing_whitespace_strip():
    out = "".join(f"line {i}   \n" for i in range(80))
    slimmed, stats = slim(out)
    assert "   \n" not in slimmed
    assert stats["applied"]


def test_under_threshold_untouched():
    out = "tiny\n\n\n\noutput"
    slimmed, stats = slim(out)
    assert slimmed == out
    assert stats == {"chars_saved": 0, "applied": False}


def test_no_noise_no_saving():
    out = "clean dense output\n" * 60  # >200 chars, nothing to strip
    slimmed, stats = slim(out)
    assert slimmed == out
    assert stats["chars_saved"] == 0
    assert stats["applied"] is False


# -- CYCLE 35F1 (critic-loop8 finding 6) ---------------------------------
# The chars-saved stat is journaled with the outcome. Before 35F1 the loop
# read an unbound `jkey` in run_turns' scope and the surrounding
# `except Exception` swallowed the NameError, so no record was ever written.

def test_slim_stat_is_journaled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from codemonkey.journal import read_thread
    from codemonkey.loop import run_turns
    from codemonkey.sandbox import ToolContext

    noisy = ("line with trailing space   \n" + "\n\n\n") * 40
    (tmp_path / "noisy.txt").write_text(noisy)
    calls = {"n": 0}

    class Turn:
        def __init__(self, content):
            self.content = content
            self.usage = {}
            self.tool_calls = []

    class Prov:
        protocol = "openai"

        def chat(self, messages, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                return Turn('TOOL_CALL: {"name": "read_file", '
                            '"arguments": {"path": "noisy.txt"}}\n')
            return Turn("done")

    ctx = ToolContext(workdir=tmp_path, sandbox="workspace-write", timeout=10)
    run_turns(Prov(), "read it", ctx, tool_protocol="prompt", max_turns=3,
              journal_thread="t-slim", journal_run="r1")
    slimmed = [r for r in read_thread("t-slim") if r.get("status") == "slimmed"]
    assert slimmed, "no slim record journaled"
    assert slimmed[0]["key"].endswith(":slim")
    assert int(slimmed[0]["output"]) > 0  # chars saved
