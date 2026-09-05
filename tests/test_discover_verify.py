"""Cycle 94 (loop 40): discoverable default-on — ASK DECIDED 2026-09-04,
verbatim: "94 no flip — ship C94 default-OFF. Revisit at loop40-final with
measured discovery hit rate and false-gate rate; flip on the number, not on
the design."

So: discovery fills the verifier ONLY when the operator configured nothing
(explicit > config > discovered > none). No declaration → unchanged.
"""

from __future__ import annotations

from codemonkey.discover import discover_verify_command, resolve_verifier


# ---------------- unit: declaration mapping ----------------

def test_pytest_ini(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    assert discover_verify_command(tmp_path) == ("pytest -q", "pytest.ini")


def test_tox_ini(tmp_path):
    (tmp_path / "tox.ini").write_text("[tox]\n")
    assert discover_verify_command(tmp_path) == ("tox", "tox.ini")


def test_setup_cfg_pytest_section(tmp_path):
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\n")
    assert discover_verify_command(tmp_path) == ("pytest -q", "setup.cfg")


def test_setup_cfg_without_pytest_section(tmp_path):
    (tmp_path / "setup.cfg").write_text("[metadata]\nname = x\n")
    assert discover_verify_command(tmp_path) == (None, "")


def test_pyproject_with_and_without(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\n')
    assert discover_verify_command(tmp_path) == ("pytest -q", "pyproject.toml")


def test_pyproject_without_pytest_config(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert discover_verify_command(tmp_path) == (None, "")


def test_package_json_test_script(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"test": "jest"}}\n')
    assert discover_verify_command(tmp_path) == ("npm test", "package.json")


def test_package_json_without_test_script(tmp_path):
    (tmp_path / "package.json").write_text('{"scripts": {"lint": "x"}}\n')
    assert discover_verify_command(tmp_path) == (None, "")


def test_makefile_test_target(tmp_path):
    (tmp_path / "Makefile").write_text("test:\n\tpytest -q\n\nlint:\n\tx\n")
    assert discover_verify_command(tmp_path) == ("make test", "Makefile")


def test_makefile_without_test_target(tmp_path):
    (tmp_path / "Makefile").write_text("lint:\n\tx\n")
    assert discover_verify_command(tmp_path) == (None, "")


def test_empty_dir_discovers_nothing(tmp_path):
    assert discover_verify_command(tmp_path) == (None, "")


def test_precedence_explicit_over_config_over_discovered(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    assert resolve_verifier("my-cmd", "cfg-cmd", tmp_path) == ("my-cmd", "explicit")
    assert resolve_verifier(None, "cfg-cmd", tmp_path) == ("cfg-cmd", "config")
    assert resolve_verifier(None, None, tmp_path) == ("pytest -q", "discovered:pytest.ini")
    assert resolve_verifier(" ", " ", tmp_path) == ("pytest -q", "discovered:pytest.ini")


# ---------------- R-I: exec auto-verifies iff declared ----------------

class Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


class WriteProv:
    protocol = "openai"

    def __init__(self):
        self.n = 0

    def chat(self, messages, system=None, **kw):
        self.n += 1
        if self.n == 1:
            return Turn('TOOL_CALL: {"name": "write_file", "arguments": '
                        '{"path": "note.txt", "content": "x"}}\n')
        return Turn("done")

    def close(self):
        pass


def _run(tmp_path, monkeypatch):
    import codemonkey.exec as exec_mod

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CODEMONKEY_TOOL_PROTOCOL", "prompt")
    monkeypatch.delenv("CODEMONKEY_VERIFY_COMMAND", raising=False)
    prov = WriteProv()
    orig = exec_mod._provider_from_config
    monkeypatch.setattr(exec_mod, "_provider_from_config",
                        lambda cfg, pn, m: (orig(cfg, pn, m)[0], prov))
    events: list = []
    code = exec_mod.run_exec(
        "Write a note", cwd=tmp_path,
        skip_git_repo_check=True, ephemeral=True, stream_deltas=False,
        stdin_cm="", sandbox="workspace-write", approval="never",
        event_sink=events, max_turns=6)
    return code, events


def test_declared_repo_auto_verifies(tmp_path, monkeypatch):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "test_ok.py").write_text("def test_ok(): pass\n")
    code, events = _run(tmp_path, monkeypatch)
    started = [e for e in events if e.get("type") == "verify.started"]
    assert started, "discovered verifier never ran"
    assert started[0]["command"] == "pytest -q"
    notices = [e for e in events if e.get("type") == "notice"
               and "discovered" in str(e.get("message", ""))]
    assert notices and "pytest.ini" in notices[0]["message"]
    assert code in (0, 1)  # the run itself is unaffected by the gate existing


def test_undeclared_repo_behavior_unchanged(tmp_path, monkeypatch):
    code, events = _run(tmp_path, monkeypatch)
    assert not [e for e in events if e.get("type") == "verify.started"]
    assert code in (0, 1)
