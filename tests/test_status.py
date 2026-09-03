"""Cycle 48 (loop15): codemonkey status — operator surface."""

from __future__ import annotations

import json
import subprocess

import pytest

from codemonkey.jobs import create, set_step
from codemonkey.spill import spill
from codemonkey.status_mod import collect, render


@pytest.fixture()
def op_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_empty_store_tolerance(op_home):
    data = collect(op_home / "build" / "eval")
    assert data["jobs"]["count"] == 0
    assert data["sessions"]["count"] == 0
    assert data["eval"]["baseline"] is None
    assert data["cost"]["runs"] == 0
    assert data["spill"]["files"] == 0
    text = render(data)
    assert "jobs: none" in text and "journal: clean" in text


def test_jobs_progress(op_home):
    j = create("ship thing", ["a", "b", "c"])
    set_step(j["id"], "a", "done")
    set_step(j["id"], "b", "failed", note="boom")
    data = collect(op_home / "build" / "eval")
    item = data["jobs"]["items"][0]
    assert item["done"] == 1 and item["failed"] == 1 and item["total"] == 3


def test_journal_classes(op_home):
    from codemonkey.journal import record

    record("tj", "outcome", tool="shell", key="k1", status="error",
           error_class="timeout")
    record("tj", "outcome", tool="shell", key="k2", status="ok")
    data = collect(op_home / "build" / "eval")
    assert data["journal"]["classes"].get("timeout") == 1
    assert data["journal"]["classes"].get("ok") == 1


def test_baseline_and_cost(op_home):
    eval_dir = op_home / "build" / "eval"
    eval_dir.mkdir(parents=True)
    (eval_dir / "baseline.json").write_text(json.dumps(
        {"suite": "s", "pass_rate": 0.9, "total_tokens": 1234}))
    from codemonkey.cost import append_to_ledger, summarize

    append_to_ledger(summarize([
        {"type": "turn.completed", "usage": {"total_tokens": 50}}]), path=None)
    data = collect(eval_dir)
    assert data["eval"]["baseline"]["pass_rate"] == 0.9
    assert data["cost"]["total_tokens"] == 50


def test_spill_bytes(op_home):
    spill("x" * 500, tool="shell")
    data = collect(op_home / "build" / "eval")
    assert data["spill"]["files"] >= 1
    assert data["spill"]["bytes"] >= 500


def test_render_includes_sections(op_home):
    create("visible job", ["s1"])
    data = collect(op_home / "build" / "eval")
    text = render(data)
    assert "visible job" in text
    assert "sessions:" in text and "cost ledger:" in text
