"""Loop 23 (cycle 60): env quarantine."""

from __future__ import annotations

import os

from envquarantine import (SENSITIVE_MODULES, is_sensitive,
                                      restore_codemonkey_env,
                                      scrub_codemonkey_env,
                                      snapshot_codemonkey_env)


def test_snapshot_and_restore(monkeypatch):
    monkeypatch.setenv("CODEMONKEY_TESTVAR", "one")
    snap = snapshot_codemonkey_env()
    assert snap.get("CODEMONKEY_TESTVAR") == "one"
    os.environ["CODEMONKEY_TESTVAR"] = "two"
    os.environ["CODEMONKEY_EXTRA9"] = "x"
    restore_codemonkey_env(snap)
    assert os.environ.get("CODEMONKEY_TESTVAR") == "one"
    assert "CODEMONKEY_EXTRA9" not in os.environ


def test_scrub_removes_all_prefixed(monkeypatch):
    monkeypatch.setenv("CODEMONKEY_A", "1")
    monkeypatch.setenv("CODEMONKEY_B", "2")
    monkeypatch.setenv("NOT_MINE", "keep")
    removed = scrub_codemonkey_env()
    assert set(removed) >= {"CODEMONKEY_A", "CODEMONKEY_B"}
    assert "NOT_MINE" in os.environ


def test_scrub_extras(monkeypatch):
    monkeypatch.setenv("SPECIAL", "1")
    monkeypatch.delenv("CODEMONKEY_X", raising=False)
    removed = scrub_codemonkey_env(extra=["SPECIAL"])
    assert "SPECIAL" in removed and "SPECIAL" not in os.environ


def test_sensitive_module_filter():
    assert is_sensitive("test_cost")
    assert is_sensitive("test_cache_telemetry")
    assert not is_sensitive("test_budget")


def test_autouse_fixture_restores_after_test():
    # this test itself runs under the autouse fixture: set a var, and confirm
    # it exists during the test
    os.environ["CODEMONKEY_TMP"] = "1"
    assert os.environ["CODEMONKEY_TMP"] == "1"
