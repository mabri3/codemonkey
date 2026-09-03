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
