"""Cycle 25 (loop5): golden suite + regression baseline.

Verify probe (plan.md): baseline written from a green run; a deliberately
broken task -> `eval --check` exit 1 naming the regression; restored -> exit 0.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from codemonkey.eval import check_regression, run_suite, write_baseline
from conftest import requires_home


def test_baseline_roundtrip(tmp_path):
    results = {
        "suite": "s", "pass_rate": 1.0, "total_tokens": 10, "wall_seconds": 1.0,
        "tasks": [{"id": "a", "ok": True}, {"id": "b", "ok": True}],
    }
    bp = tmp_path / "baseline.json"
    write_baseline(results, bp)
    data = json.loads(bp.read_text())
    assert data["tasks"] == {"a": {"ok": True}, "b": {"ok": True}}
    ok, reg = check_regression(results, bp)
    assert ok and reg == []


def test_regression_detected(tmp_path):
    bp = tmp_path / "baseline.json"
    write_baseline({"suite": "s", "pass_rate": 1.0, "total_tokens": 0,
                    "wall_seconds": 0, "tasks": [{"id": "a", "ok": True}]}, bp)
    now = {"suite": "s", "pass_rate": 0.0, "total_tokens": 0, "wall_seconds": 0,
           "tasks": [{"id": "a", "ok": False}]}
    ok, reg = check_regression(now, bp)
    assert not ok
    assert any("a" in r for r in reg)
    assert any("pass_rate dropped" in r for r in reg)


def test_improvement_never_fails(tmp_path):
    bp = tmp_path / "baseline.json"
    write_baseline({"suite": "s", "pass_rate": 0.0, "total_tokens": 0,
                    "wall_seconds": 0, "tasks": [{"id": "a", "ok": False}]}, bp)
    now = {"suite": "s", "pass_rate": 1.0, "total_tokens": 0, "wall_seconds": 0,
           "tasks": [{"id": "a", "ok": True}]}
    ok, reg = check_regression(now, bp)
    assert ok  # improvement is not a regression


def test_no_baseline_is_not_a_regression(tmp_path):
    now = {"suite": "s", "pass_rate": 0.0, "total_tokens": 0, "wall_seconds": 0,
           "tasks": [{"id": "a", "ok": False}]}
    ok, reg = check_regression(now, tmp_path / "missing.json")
    assert ok and reg == []


# ---------------- CLI end-to-end (patched exec via env-faked provider) ------

def _run_eval_cli(args, cwd):
    return subprocess.run(
        ["uv", "run", "codemonkey", "eval"] + args,
        capture_output=True, text=True, timeout=420, cwd=cwd,
    )


@requires_home
def test_cli_check_regression_flow(tmp_path, monkeypatch):
    """Live CLI: green run -> write baseline -> broken suite -> --check exit 1."""
    repo = Path("/Users/bharris/Programs/CodeMonkey")
    monkeypatch.chdir(repo)

    suite_path = tmp_path / "cli-suite.yaml"
    suite_path.write_text(yaml.safe_dump({
        "name": "cli-flow",
        "tasks": [{"id": "ping", "prompt": "Reply with exactly: ping",
                   "expect_stdout_contains": ["ping"], "expect_exit": 0}],
    }))
    baseline = tmp_path / "baseline.json"
    out = tmp_path / "eval"

    r1 = _run_eval_cli([str(suite_path), "--check", "--baseline", str(baseline),
                        "--out", str(out), "--write-baseline"], cwd=repo)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert baseline.is_file()

    # now break the expectation: suite demands a word the model won't say
    suite_path.write_text(yaml.safe_dump({
        "name": "cli-flow",
        "tasks": [{"id": "ping", "prompt": "Reply with exactly: ping",
                   "expect_stdout_contains": ["zebra-not-said"], "expect_exit": 0}],
    }))
    r2 = _run_eval_cli([str(suite_path), "--check", "--baseline", str(baseline),
                        "--out", str(out)], cwd=repo)
    assert r2.returncode == 1
    assert "REGRESSIONS" in r2.stdout + r2.stderr or "pass_rate dropped" in r2.stdout + r2.stderr