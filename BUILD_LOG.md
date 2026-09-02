# BUILD_LOG — CodeMonkey

## 2026-09-01 — CYCLE 1: repo scaffold + config layer

- **Files changed:** `pyproject.toml`, `.python-version` (3.11), `.gitignore`,
  `README.md`, `src/codemonkey/__init__.py` (v0.1.0), `src/codemonkey/cli.py`
  (Typer app, `--version`, `config` cmd), `src/codemonkey/config.py`
  (merge chain: defaults → `~/.codemonkey/config.yaml` → `.codemonkey.yaml` →
  `.env` (project then `~/.codemonkey/.env`) → env vars → CLI overrides;
  sanitizing renderer; validation for enums/strategies),
  `tests/test_config.py` (10 tests), `uv.lock`.
- **Git:** repo initialized; repo-local identity `Brian Harris
  <bharris@Brians-MacBook-Air.local>`.
- **Tests run:** `uv run pytest -q` → **10 passed, 0 failed**.
- **Probe results (literal):**
  - `uv run codemonkey --version` → exit 0, stdout `codemonkey 0.1.0`
    (matches `codemonkey \d+\.\d+\.\d+`).
  - `uv run codemonkey config` → exit 0, stdout contains
    `http://192.168.50.113:8080/v1`; `grep -c 'sk-'` → 0.
  - Extras verified early (A3/A13 shape): `CODEMONKEY_MODEL=override-test`
    shows `model: override-test`; `CODEMONKEY_PROVIDER=anthropic` flips
    `default_provider: anthropic` with `claude-sonnet-4-5`; invalid
    `strategies.compaction: bogus` → exit 2, stderr lists
    `summarizing` + `sliding-window`.
- **Secrets:** `api_key` values masked (`***`) in `config` output; `sk-`
  pattern never rendered; `api_key_env` pointers left visible on purpose.
  `.env` gitignored.
- **Known issues:** none. Remaining subcommands (`exec`, `review`,
  `sessions`, `models`) land in their own cycles per plan.
- **Next step:** CYCLE 2 — provider layer (OpenAI + Anthropic, raw
  httpx, SSE) + `models` command. Verify via mocked HTTP pytest (≥8 tests)
  + live `uv run codemonkey models` containing the Qwen model name.
