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

## 2026-09-02 — CYCLE 4: tool protocol + agent loop

Recovery note: this tick started with uncommitted provider edits (an
interrupted CYCLE-4 worker) and CYCLE 2/3 commits (0b1ce0c, 9a16629) whose
plan.md checkboxes/BUILD_LOG entries had never been written by their ticks.
Fixed their state here: checkboxes 2–4 marked `[x]`; cycle-4 commit below.

- **Resumed and finished partial work:** native tool-call extraction had been
  added (`ChatTurn.tool_calls`; OpenAI `message.tool_calls` + streaming
  accumulation; Anthropic non-streaming `tool_use` + streaming
  `content_block_start`/`input_json_delta`/`content_block_stop`). Verified and
  fixed its per-instance-state wart (`self._tool_raw` leakage → local dicts) +
  PEP8 blank lines.
- **Files changed:** `src/codemonkey/protocol.py` (`TOOL_CALL:` prompt
  protocol — `prompt_block()` advertises `tools.SPECS`; `parse_tool_calls()`
  returns `(calls, prose)`; tolerant of fences, a bare marker + fenced body,
  multi-call, malformed JSON as error entries),
  `src/codemonkey/native.py` (OpenAI `tools` wire schema + tool-result msg),
  `src/codemonkey/loop.py` (`run_turns()` — messages, max_turns bail with
  error event, soft per-turn `on_event` callbacks incl.
  tool.started/tool.completed; `tool_protocol: auto` catches the
  tools-parameter HTTP 4xx/5xx, retries the same turn with the prompt
  protocol, remembers the fallback per provider — the A9 mechanic),
  `src/codemonkey/providers/{base,openai,anthropic}.py` (native extraction,
  resumed), `tests/test_protocol.py` (16 tests), `features.html` (created,
  rule 11, backfills cycles 1–4).
- **Tests run (literal):** `uv run pytest tests/test_protocol.py -q` →
  **16 passed** (verify: ≥8). Full suite `uv run pytest -q` → **73 passed,
  0 failed** (57 pre-existing + 16 new).
- **Known issues:** none. Live A9 end-to-end lands with cycle 5/10 (the loop
  is exercised here over a scripted provider replaying the verified llama.cpp
  500-on-`tools` behaviour).
- **Next step:** CYCLE 5 — `exec` core (text mode, stdin `-`, `--json` JSONL
  event stream, git-repo guard, exit codes, `--output-last-message` tee);
  LIVE probe: pong.
