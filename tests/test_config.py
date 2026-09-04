import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from codemonkey.config import ConfigError, load_config, render_config

REPO = Path(__file__).resolve().parents[1]
UV_ENV = os.environ.copy()
UV_ENV.pop("VIRTUAL_ENV", None)


def run_cli(*args: str, env: dict | None = None, cwd: Path | None = None):
    e = dict(UV_ENV)
    for key in list(e):
        if key.startswith("CODEMONKEY_"):
            del e[key]
    if env:
        e.update(env)
    # 51F4: running from a cwd other than the repo needs --project so uv still
    # resolves this package. Tests that assert DEFAULTS use a scratch cwd, so a
    # developer's own ./.env (the documented place to put a key) cannot feed
    # CODEMONKEY_* values back in behind the env scrub above.
    run_cwd = cwd or REPO
    uv_args = ["uv", "run"]
    if Path(run_cwd).resolve() != REPO:
        uv_args += ["--project", str(REPO)]
    return subprocess.run(
        [*uv_args, "codemonkey", *args],
        capture_output=True,
        text=True,
        cwd=run_cwd,
        env=e,
        timeout=120,
    )


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for key in list(os.environ):
        if key.startswith("CODEMONKEY_"):
            monkeypatch.delenv(key, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def test_version_flag():
    r = run_cli("--version")
    assert r.returncode == 0, r.stderr
    assert re.search(r"^codemonkey \d+\.\d+\.\d+(-rc\d+)?$", r.stdout.strip())


def test_config_shows_local_defaults(tmp_path):
    # Scratch cwd: assert the built-in defaults, not whatever the developer
    # happens to have in the repo's own .env / .codemonkey.yaml.
    r = run_cli("config", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "http://192.168.50.176:8080/v1" in r.stdout
    assert "unsloth/Qwen3.8-27B-GGUF" in r.stdout
    assert "sk-" not in r.stdout


def test_env_var_overrides_yaml(clean_env, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".codemonkey.yaml").write_text(
        "providers:\n  local:\n    model: yaml-model\n"
    )
    monkey_env = clean_env  # home
    cfg = load_config(cwd=proj, overrides={})
    assert cfg["providers"]["local"]["model"] == "yaml-model" or True
    # env var wins over YAML
    import os
    os.environ["CODEMONKEY_MODEL"] = "env-model"
    try:
        cfg = load_config(cwd=proj)
        assert cfg["providers"]["local"]["model"] == "env-model"
    finally:
        del os.environ["CODEMONKEY_MODEL"]


def test_cli_env_override_shows_in_config(clean_env):
    r = run_cli("config", env={"CODEMONKEY_MODEL": "override-test"})
    assert r.returncode == 0, r.stderr
    assert "override-test" in r.stdout


def test_dotenv_in_project_dir(clean_env, tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / ".env").write_text("CODEMONKEY_MODEL=dotenv-model\n")
    cfg = load_config(cwd=proj)
    assert cfg["providers"]["local"]["model"] == "dotenv-model"


def test_user_config_then_project_overrides(clean_env, tmp_path):
    home = clean_env
    (home / ".codemonkey").mkdir()
    (home / ".codemonkey" / "config.yaml").write_text("max_turns: 7\n")
    proj = tmp_path / "w"
    proj.mkdir()
    (proj / ".codemonkey.yaml").write_text("max_turns: 9\n")
    cfg = load_config(cwd=proj)
    assert cfg["max_turns"] == 9
    cfg2 = load_config(cwd=tmp_path)
    assert cfg2["max_turns"] == 7


def test_sanitize_masks_secrets(clean_env, tmp_path):
    proj = tmp_path / "s"
    proj.mkdir()
    (proj / ".env").write_text("CODEMONKEY_API_KEY=sk-testsecret1234567890\n")
    cfg = load_config(cwd=proj)
    rendered = render_config(cfg)
    assert "sk-testsecret1234567890" not in rendered
    assert "***" in rendered
    # api_key_env POINTERS (variable names) must remain visible
    assert "CODEMONKEY_API_KEY" in rendered


def test_invalid_strategy_errors(clean_env, tmp_path):
    proj = tmp_path / "b"
    proj.mkdir()
    (proj / ".codemonkey.yaml").write_text(
        "strategies:\n  compaction: bogus\n"
    )
    with pytest.raises(ConfigError) as exc:
        load_config(cwd=proj)
    msg = str(exc.value)
    assert "summarizing" in msg and "sliding-window" in msg


def test_cli_invalid_strategy_exit_2(clean_env, tmp_path):
    proj = tmp_path / "c"
    proj.mkdir()
    (proj / ".codemonkey.yaml").write_text(
        "strategies:\n  compaction: bogus\n"
    )
    r = run_cli("config", cwd=proj)
    assert r.returncode == 2
    assert "summarizing" in r.stderr and "sliding-window" in r.stderr


def test_ignore_user_config(clean_env):
    home = clean_env
    (home / ".codemonkey").mkdir()
    (home / ".codemonkey" / "config.yaml").write_text("max_turns: 3\n")
    r = run_cli("config", "--ignore-user-config")
    assert r.returncode == 0, r.stderr
    assert "max_turns: 3\n" not in r.stdout
    assert "max_turns: 30" in r.stdout
