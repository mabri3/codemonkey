"""Loop 21 (cycle 58): run digest."""

from __future__ import annotations

import pytest

from codemonkey.digest import build_digest, render_digest
from codemonkey.journal import record


@pytest.fixture()
def dhome(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_empty_thread_tolerance(dhome):
    d = build_digest("ghost-thread")
    assert d["tool_counts"] == {} and d["failures"] == []
    text = render_digest(d)
    assert "tools: none" in text and "failures: none" in text


def test_tool_counts(dhome):
    record("td", "intent", tool="shell", key="k1", status="ok")
    record("td", "intent", tool="shell", key="k2", status="ok")
    record("td", "intent", tool="write_file", key="k3", status="ok")
    d = build_digest("td")
    assert d["tool_counts"] == {"shell": 2, "write_file": 1}
    text = render_digest(d)
    assert "shell×2" in text and "write_file×1" in text


def test_failure_section(dhome):
    record("tf", "outcome", tool="edit_file", key="k", status="error",
           error_class="schema_mismatch", output="missing 'path'")
    d = build_digest("tf")
    assert d["failures"][0]["error_class"] == "schema_mismatch"
    text = render_digest(d)
    assert "failures:" in text and "[schema_mismatch]" in text


def test_route_fallback_flag(dhome):
    record("tr", "outcome", tool="route", key="k", status="model_unload_fallback",
           output="local/unsloth m1")
    d = build_digest("tr")
    assert any("model_unload_fallback" in f for f in d["flags"])


def test_json_shape(dhome):
    record("tj", "intent", tool="shell", key="k", status="ok")
    d = build_digest("tj")
    assert set(d) == {"thread", "tool_counts", "failures", "flags", "records"}


def test_render_header(dhome):
    d = build_digest("tx")
    assert render_digest(d).startswith("# run digest: tx")
