"""Cycle 54 (loop18): unload-fallback rerouting."""

from __future__ import annotations

import pytest

from codemonkey.unload import fallback_route, is_model_unloaded_error


class Turn:
    def __init__(self, content):
        self.content = content
        self.usage = {"total_tokens": 1}
        self.tool_calls = []
        self.reasoning = ""


class UnloadedError(Exception):
    pass


def test_unload_sentences_detected():
    assert is_model_unloaded_error(
        Exception('HTTP 400: {"error":{"message":"No model loaded. Call POST /inference/load first."}}'))
    assert is_model_unloaded_error(Exception("model not loaded for this request"))
    assert is_model_unloaded_error(Exception("Please load the model first"))
    assert is_model_unloaded_error(Exception("no model is loaded"))
    assert not is_model_unloaded_error(Exception("auth failed (401)"))
    assert not is_model_unloaded_error(Exception("HTTP 500: tools parameter unsupported"))
    assert not is_model_unloaded_error(Exception("transport timeout"))


def test_fallback_route_shape():
    r = fallback_route("local", "default-m")
    assert r == {"provider": "local", "model": "default-m",
                 "reason": "model_unload_fallback"}


def _exec_with_unload(monkeypatch, tmp_path):
    """Run real exec; the primary provider raises unloaded on the FIRST chat
    then succeeds; verify the retry happened (2 calls) and no exception."""
    import codemonkey.exec as exec_mod
    import codemonkey.config as cfg_mod
    import codemonkey.loop as loop_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("x")

    real_lc = cfg_mod.load_config

    def fake_lc(**kw):
        merged = real_lc(**kw)
        merged["providers"]["local"] = {
            "protocol": "openai", "base_url": "http://x/v1", "model": "m1",
            "api_key_env": "", "tool_protocol": "auto"}
        merged["default_provider"] = "local"
        return merged

    monkeypatch.setattr(cfg_mod, "load_config", fake_lc)

    calls = {"n": 0}
    notices = []

    class FP:
        protocol = "openai"

        def __init__(self):
            self.model = "m1"

        def close(self):
            pass

        def chat(self, *a, **kw):
            return Turn("chat-ok")

    def fake_pfg(cfg, name, mdl):
        name = name or cfg.get("default_provider") or "local"
        return name, FP()

    def fake_run_turns(prov, prompt, ctx, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnloadedError('HTTP 400: No model loaded. Call POST /inference/load first.')
        t = Turn("recovered")
        t.reasoning = ""
        t.all_messages = [{"role": "user", "content": prompt},
                          {"role": "assistant", "content": "done"}]
        return t

    monkeypatch.setattr(exec_mod, "_provider_from_config", fake_pfg)
    monkeypatch.setattr(loop_mod, "run_turns", fake_run_turns)
    code = exec_mod.run_exec("work", ephemeral=True, stdin_cm="",
                             skip_git_repo_check=True)
    return code, calls, notices


def test_unload_retried_once_then_success(tmp_path, monkeypatch):
    code, calls, notices = _exec_with_unload(monkeypatch, tmp_path)
    assert calls["n"] == 2
    assert code == 0
