"""Loop 24 (cycle 61): delegate role presets."""

from __future__ import annotations

from codemonkey.rolepresets import apply_to_cmd, resolve_role_preset


PRESETS = {
    "critic": {"provider": "local", "model": "big-moe"},
    "verifier": {"provider": "local", "model": "dense-m"},
}


def test_preset_resolution():
    r = resolve_role_preset(PRESETS, "critic", default_model="d")
    assert r == {"provider": "local", "model": "big-moe", "preset": "critic"}


def test_unknown_role_falls_through():
    r = resolve_role_preset(PRESETS, "implementer", default_model="d")
    assert r == {"provider": "local", "model": "d", "preset": ""}


def test_empty_config_no_change():
    r = resolve_role_preset(None, "critic", default_model="d")
    assert r["model"] == "d" and r["preset"] == ""


def test_apply_overlays_cmd_args():
    cmd = {"task": "review it"}
    out = apply_to_cmd(cmd, {"provider": "local", "model": "big-moe"})
    assert out["model"] == "big-moe" and out["provider"] == "local"
    assert cmd == {"task": "review it"}  # original untouched


def test_journal_contract():
    # delegate journals the preset application via the route record format
    from codemonkey.journal import record, read_thread

    import tempfile, os
    os.environ.setdefault("HOME", tempfile.mkdtemp())
    r = resolve_role_preset(PRESETS, "verifier", default_model="d")
    record("t61", "outcome", tool="route", key="run61", status="applied",
           output=f"{r['provider']}/{r['model']} preset={r['preset']}")
    recs = read_thread("t61")
    assert any("preset=verifier" in str(x.get("output")) for x in recs)
