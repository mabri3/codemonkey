"""R32: best-of-N with an execution verifier."""

from __future__ import annotations

import pytest

from codemonkey.bestofn import best_of_n, score_with_verifier


def test_verifier_pass_and_fail(tmp_path):
    ok, out = score_with_verifier("true", tmp_path)
    assert ok
    ok2, out2 = score_with_verifier("exit 3", tmp_path)
    assert not ok2 and "timeout" not in out2


def test_first_passing_candidate_wins(tmp_path):
    applied = []

    def apply(text):
        applied.append(text)

    res = best_of_n(["bad", "good"], verify_command="true",
                    workdir=tmp_path, apply_fn=apply)
    assert res["ok"] is True and res["index"] == 0
    assert res["tries"] == 1


def test_none_pass_returns_evidence(tmp_path):
    res = best_of_n(["a", "b"], verify_command="exit 2", workdir=tmp_path)
    assert res["ok"] is False and res["candidates_scored"] == 2
    assert isinstance(res["last_fail_tail"], str)


def test_scored_in_order(tmp_path):
    seen = []

    res = best_of_n(["one", "two", "three"], verify_command="true",
                    workdir=tmp_path, apply_fn=lambda t: seen.append(t))
    assert res["index"] == 0 and len(seen) == 1
