"""Cycle 47 (loop14): availability failover."""

from __future__ import annotations

import pytest

from codemonkey.permissions import _PATH_TOOLS  # noqa: F401 (sanity)


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []
        self.reasoning = ""


def _run_exec_with_failover(monkeypatch, tmp_path, primary_raises, fallback_raises=None,
                            fallback_name="fb"):
    """Run the real exec path with stubbed providers via the config."""
    import codemonkey.exec as exec_mod
    from codemonkey.exec import ExecUsageError

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("x")

    cfg_extra = {
        "providers": {
            "primary": {"protocol": "openai", "base_url": "http://primary/v1",
                        "model": "m1", "tool_protocol": "auto"},
            fallback_name: {"protocol": "openai", "base_url": "http://fb/v1",
                            "model": "m2", "tool_protocol": "auto"},
        },
        "default_provider": "primary",
        "fallback_provider": fallback_name,
    }

    import codemonkey.config as cfg_mod

    real_lc = cfg_mod.load_config

    def fake_lc(**kw):
        merged = real_lc(**kw)
        merged["providers"].update(cfg_extra["providers"])
        merged["default_provider"] = "primary"
        merged["fallback_provider"] = fallback_name
        return merged

    monkeypatch.setattr(cfg_mod, "load_config", fake_lc)

    calls = {"primary": 0, "fb": 0}
    built = []

    class FakeProvider:
        protocol = "openai"

        def __init__(self, name):
            self.name = name
            self.model = "m"

        def close(self):
            pass

        def chat(self, messages, **kw):
            calls[self.name] += 1
            if self.name == "primary" and primary_raises is not None:
                raise primary_raises
            if self.name == fallback_name and fallback_raises is not None:
                raise fallback_raises
            return Turn("fallback-ok")

    real_pfg = exec_mod._provider_from_config

    def fake_pfg(cfg, name, model):
        built.append(name)
        return name, FakeProvider(name)

    monkeypatch.setattr(exec_mod, "_provider_from_config", fake_pfg)

    errors = []
    code = None
    try:
        code = exec_mod.run_exec("do it", ephemeral=True, stdin_cm="",
                                 provider_name="primary",
                                 skip_git_repo_check=True)
        errors.append(None)
    except ExecUsageError as exc:
        errors.append(exc)
    except Exception as exc:  # transport-class errors propagate if no failover
        errors.append(exc)
        print("EXEC-RAISED:", type(exc).__name__, str(exc)[:200])
    return code, errors[0], calls, built


def test_failover_on_transport_error(tmp_path, monkeypatch):
    from codemonkey.providers.base import ProviderError

    code, err, calls, built = _run_exec_with_failover(
        monkeypatch, tmp_path, ProviderError("transport error contacting http://primary/v1"))
    assert calls["primary"] == 1
    assert calls["fb"] == 1
    assert built == ["primary", "fb"]
    assert code == 0


def test_failover_on_timeout(tmp_path, monkeypatch):
    from codemonkey.providers.base import ProviderError

    code, err, calls, built = _run_exec_with_failover(
        monkeypatch, tmp_path, ProviderError("request timed out after 30s"))
    assert calls["fb"] == 1
    assert code == 0


def test_no_failover_on_auth(tmp_path, monkeypatch):
    from codemonkey.providers.base import AuthError

    code, err, calls, built = _run_exec_with_failover(
        monkeypatch, tmp_path, AuthError("auth failed (401)", status=401))
    assert calls["fb"] == 0
    assert err is not None  # propagates


def test_no_failover_on_tools_500(tmp_path, monkeypatch):
    from codemonkey.providers.base import ProviderError

    code, err, calls, built = _run_exec_with_failover(
        monkeypatch, tmp_path,
        ProviderError("HTTP 500: unsupported tools parameter", status=500))
    assert calls["fb"] == 0  # protocol fallback handles this, not failover
    assert err is not None or code == 0


def test_unknown_fallback_provider_rejected(tmp_path, monkeypatch):
    import codemonkey.config as cfg_mod
    import codemonkey.exec as exec_mod
    from codemonkey.exec import ExecUsageError

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("x")

    real_lc = cfg_mod.load_config

    def fake_lc(**kw):
        merged = real_lc(**kw)
        merged["providers"] = {"primary": {"protocol": "openai",
                                            "base_url": "http://p/v1",
                                            "model": "m",
                                            "tool_protocol": "auto"}}
        merged["default_provider"] = "primary"
        merged["fallback_provider"] = "ghost"
        return merged

    monkeypatch.setattr(cfg_mod, "load_config", fake_lc)
    with pytest.raises(ExecUsageError, match="ghost"):
        exec_mod.run_exec("do it", ephemeral=True, stdin_cm="",
                          provider_name="primary", skip_git_repo_check=True)
