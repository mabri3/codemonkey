"""Cycle 49 (loop16): secret redaction + supply-chain audit + threat model."""

from __future__ import annotations

import json
import os

import pytest

from codemonkey.journal import journal_path, record
from codemonkey.redact import (needles_from_config, redact_eval_results,
                               redact_journal_file, redact_text)


SECRET = "rk-test-key-1234567890abcdef"


@pytest.fixture()
def rhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_key_shaped_redaction():
    text = f"error calling {SECRET} failed"
    out, hits = redact_text(text, [])
    assert SECRET not in out
    assert "[REDACTED]" in out
    assert hits == 1


def test_config_needles_redacted(rhome, monkeypatch):
    monkeypatch.setenv("CODEMONKEY_API_KEY", SECRET)
    cfg = {"providers": {"local": {"api_key_env": "CODEMONKEY_API_KEY"}}}
    needles = needles_from_config(cfg)
    assert SECRET in needles
    out, hits = redact_text(f"leak {SECRET} end", needles)
    assert SECRET not in out and hits == 1


def test_redaction_noop_when_clean(rhome):
    out, hits = redact_text("perfectly clean text", [])
    assert out == "perfectly clean text" and hits == 0


def test_journal_redaction_repair(rhome):
    record("t1", "outcome", tool="shell", key="k1", status="ok",
           output=f"token {SECRET} leaked")
    p = journal_path("t1")
    assert SECRET in p.read_text()  # written before redaction existed
    n = redact_journal_file(p, [])
    assert n == 1
    assert SECRET not in p.read_text()
    # the record still parses
    import json as j
    rec = j.loads(p.read_text().splitlines()[-1])
    assert "[REDACTED]" in rec["output"]


def test_eval_results_redaction(rhome):
    results = {"tasks": [{"id": "t", "stdout": f"out {SECRET} out", "ok": True}]}
    data, n = redact_eval_results(results, [])
    assert SECRET not in data["tasks"][0]["stdout"]
    assert n == 1


def test_threat_model_exists():
    from pathlib import Path

    p = Path(__file__).parent.parent / "THREAT_MODEL.md"
    assert p.is_file()
    text = p.read_text()
    for section in ("Promised", "NOT promised", "Operator guidance"):
        assert section in text
    assert "sandbox-exec" in text  # the deprecation rationale is recorded


def test_lockfile_committed():
    from pathlib import Path

    root = Path(__file__).parent.parent
    lock = root / "uv.lock"
    assert lock.is_file(), "uv.lock must be committed for reproducible builds"
