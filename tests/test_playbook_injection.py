"""loop47 cycle 109 — `context = playbook`: admitted entries reach the prompt,
and NOTHING else does.

The byte-diffs ARE the control (equality, not substring — a substring check
would miss added bytes):

* static prompt: unchanged by this cycle (baseline);
* playbook mode with an empty, quarantined-only, or evicted store is
  BYTE-EQUAL to static — the absence of quarantined text is the proof the
  gate holds (and the break-verification script patches the gate and watches
  these tests go red);
* playbook mode with admitted entries is byte-equal to static PLUS exactly
  the rendered block;
* the budget is enforced BEFORE rendering: budget=0 is byte-equal to static
  with an accounting line that names the omission; a partial budget includes
  exactly the fitting entries and the line counts them (absent budget =
  unlimited, and the line says that too).
"""

from __future__ import annotations

from codemonkey import playbook


class RecordingProvider:
    protocol = "openai"

    def __init__(self):
        self.systems = []

    def chat(self, messages, system=None, **kw):
        self.systems.append(system or "")
        from codemonkey.providers.base import ChatTurn

        return ChatTurn(content="ok", usage={"total_tokens": 1})


def _run_real_exec(tmp_path) -> list[str]:
    """Drive the REAL run_exec with a recording provider (no network)."""
    import codemonkey.exec as exec_mod

    prov = RecordingProvider()
    orig = exec_mod._provider_from_config

    def patched(cfg, provider_name, model):
        name, _ = orig(cfg, provider_name, model)
        return name, prov

    exec_mod._provider_from_config = patched
    try:
        code = exec_mod.run_exec(
            "Say ok.",
            cwd=tmp_path,
            skip_git_repo_check=True,
            ephemeral=True,
            stream_deltas=False,
            stdin_cm="",
        )
    finally:
        exec_mod._provider_from_config = orig
    assert code == 0
    assert prov.systems, "the provider must have been called"
    return prov.systems


def _delta(text, prov_run="r"):
    return {"kind": "strategy", "section": "tools", "text": text,
            "provenance": {"run_id": prov_run, "session_id": "s",
                           "taint_free": True}}


def _admit(workdir, text):
    playbook.merge_deltas(workdir, [_delta(text)])
    eid = [e["id"] for e in playbook.list_entries(workdir)
           if e["text"] == text][0]
    playbook.set_status(workdir, eid, "admitted", reason="test")
    return eid


def _systems(tmp_path, monkeypatch, mode, budget=None):
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", mode)
    if budget is None:
        monkeypatch.delenv("CODEMONKEY_PLAYBOOK_BUDGET", raising=False)
    else:
        monkeypatch.setenv("CODEMONKEY_PLAYBOOK_BUDGET", str(budget))
    return _run_real_exec(tmp_path)


def test_playbook_mode_empty_store_is_byte_equal_to_static(tmp_path, monkeypatch):
    static = _systems(tmp_path, monkeypatch, "static")
    pb = _systems(tmp_path, monkeypatch, "playbook")
    assert pb == static  # byte-for-byte: the strategy adds nothing by itself


def test_quarantined_and_evicted_entries_never_render(tmp_path, monkeypatch):
    static = _systems(tmp_path, monkeypatch, "static")
    _admit(tmp_path, "quarantined-then-evicted line alpha beta")
    eid = playbook.list_entries(tmp_path)[0]["id"]
    playbook.set_status(tmp_path, eid, "evicted", reason="later probe failed")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "playbook")
    pb = _run_real_exec(tmp_path)
    assert pb == static, "an evicted entry must not reach the prompt"

    playbook.merge_deltas(tmp_path, [_delta("fresh quarantine line gamma")])
    pb2 = _run_real_exec(tmp_path)
    assert pb2 == static, "a quarantined entry must not reach the prompt"


def test_admitted_entries_render_exactly_the_block(tmp_path, monkeypatch):
    static = _systems(tmp_path, monkeypatch, "static")
    _admit(tmp_path, "alpha beta gamma")
    _admit(tmp_path, "delta epsilon zeta")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "playbook")
    pb = _run_real_exec(tmp_path)
    block = ("## Playbook (admitted)\n"
             "- [strategy/tools] alpha beta gamma\n"
             "- [strategy/tools] delta epsilon zeta")
    # exactly the block added on a "\n\n" boundary — nothing else differs, in
    # both directions (removal reproduces the static prompt byte-for-byte)
    assert block in pb[0]
    assert pb[0].replace("\n\n" + block, "", 1) == static[0]
    # and it sits inside the context region: after memory, before the tool
    # protocol section — not appended past the end of the prompt
    assert pb[0].index("## Memory") < pb[0].index(block) < pb[0].index("You have tools.")


def test_budget_zero_omits_block_and_the_line_names_it(tmp_path, monkeypatch, capsys):
    static = _systems(tmp_path, monkeypatch, "static")
    _admit(tmp_path, "alpha beta gamma")
    _admit(tmp_path, "delta epsilon zeta")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "playbook")
    monkeypatch.setenv("CODEMONKEY_PLAYBOOK_BUDGET", "0")
    pb = _run_real_exec(tmp_path)
    err = capsys.readouterr().err
    assert pb == static                                   # absence, not a note
    assert "0/2 entries injected" in err                  # the accounting line
    assert "budget: 0 words" in err and "block omitted" in err


def test_partial_budget_includes_only_fitting_entries(tmp_path, monkeypatch, capsys):
    static = _systems(tmp_path, monkeypatch, "static")
    _admit(tmp_path, "alpha beta gamma")     # line costs 5 words
    _admit(tmp_path, "delta epsilon zeta")   # 5 more would exceed 6
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "playbook")
    monkeypatch.setenv("CODEMONKEY_PLAYBOOK_BUDGET", "6")
    pb = _run_real_exec(tmp_path)
    err = capsys.readouterr().err
    block = ("## Playbook (admitted)\n"
             "- [strategy/tools] alpha beta gamma")
    assert pb[0].replace("\n\n" + block, "", 1) == static[0]
    assert "delta epsilon zeta" not in pb[0]      # held entry never renders
    assert "1/2 entries injected" in err and "1 held" in err


def test_absent_budget_is_unlimited_and_says_so(tmp_path, monkeypatch, capsys):
    _admit(tmp_path, "alpha beta gamma")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "playbook")
    monkeypatch.delenv("CODEMONKEY_PLAYBOOK_BUDGET", raising=False)
    _run_real_exec(tmp_path)
    err = capsys.readouterr().err
    assert "budget: unlimited" in err and "1/1 entries injected" in err


def test_corrupt_store_fails_closed_and_audible(tmp_path, monkeypatch, capsys):
    static = _systems(tmp_path, monkeypatch, "static")
    p = playbook.store_path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json")
    monkeypatch.setenv("CODEMONKEY_STRATEGY_CONTEXT", "playbook")
    pb = _run_real_exec(tmp_path)
    err = capsys.readouterr().err
    assert pb == static and "injection REFUSED" in err
