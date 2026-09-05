# Spec — CodeMonkey (`codemonkey`)

Python 3.11 CLI (uv + Typer + Rich + httpx). Coding-agent CLI that runs
against OpenAI-style **and** Anthropic-style endpoints, defaulting to the
local llama.cpp server. Non-interactive by design (scriptable by Claude
Code / Codex / CI), with an interactive rich REPL when run bare.

## Providers & configuration

Multi-provider, selected per provider block; no SDK lock-in (raw httpx,
hand-rolled SSE parsing so adding a provider = config, not code):

```yaml
# ~/.codemonkey/config.yaml  (global) — .codemonkey.yaml (project) overrides — .env overrides both — CLI flags override all
providers:
  local:
    protocol: openai            # openai | anthropic
    base_url: http://192.168.50.176:8080/v1
    model: Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf
    api_key_env: CODEMONKEY_API_KEY
    tool_protocol: auto         # auto | native | prompt (auto = native if the protocol+server supports it, else prompt)
  anthropic:
    protocol: anthropic
    base_url: https://api.anthropic.com
    model: claude-sonnet-4-5
    api_key_env: ANTHROPIC_API_KEY
default_provider: local
sandbox: workspace-write        # read-only | workspace-write | danger-full-access
approval: on-request            # untrusted | on-request | never
max_turns: 30
timeout_seconds: 300
```

`.env` (project dir, then `~/.codemonkey/.env`) supplies secrets/overrides:
`CODEMONKEY_API_KEY`, `CODEMONKEY_BASE_URL`, `CODEMONKEY_MODEL`,
`CODEMONKEY_PROVIDER`, `CODEMONKEY_SANDBOX`, `CODEMONKEY_APPROVAL`.

## Commands & flags (modeled on `codex exec` / `agy` / Claude Code)

| Command | Behavior |
|---|---|
| `codemonkey` (bare) | interactive rich REPL (prompted) |
| `codemonkey exec [PROMPT]` | non-interactive; stdout = final response only, progress/diagnostics on stderr; stdin piped = extra context, `-` = stdin is the prompt |
| `codemonkey exec resume [--last \| THREAD_ID] [PROMPT]` | continue a persisted session |
| `codemonkey review [--uncommitted \| --base X \| --commit SHA]` | non-interactive diff review |
| `codemonkey sessions` | list persisted sessions (thread_id, time, first prompt) |
| `codemonkey config` | print effective merged config (sanitized: no secrets) |
| `codemonkey models` | list models from the active provider (`/v1/models` or Anthropic-equivalent) |
| `codemonkey --version` | version string |

exec flags: `--json` (JSONL event stream on stdout),
`-o/--output-last-message FILE`, `--output-schema FILE` (JSON Schema; final
response validated, one retry on failure), `--sandbox`,
`-a/--ask-for-approval`, `--provider`, `--model`, `-C/--cd`, `--add-dir`,
`--skip-git-repo-check`, `--ephemeral` (no session persistence),
`--max-turns`, `--timeout`, `--dangerously-bypass-approvals-and-sandbox`,
`--ignore-user-config`.

JSONL event contract (codex-style, one JSON object per line on stdout):
`thread.started{thread_id}`, `turn.started`, `item.started`/`item.completed`
with `item:{id,type,...}` (types: `agent_message`, `reasoning`,
`command_execution`, `file_change`, `plan`), `turn.completed{usage}`,
`error{message}`. In text mode, the same items render as human lines on
stderr.

Exit codes: `0` success · `1` run error · `2` usage/auth error.

## Tool protocol

The llama.cpp server rejects the OpenAI `tools` parameter (verified 500),
so tool calling has two implementations, selected per provider
(`tool_protocol`):

- **native** — OpenAI `tools` field / Anthropic `tool_use` blocks, used when
  the protocol+server supports it.
- **prompt** (always available) — the system prompt advertises the tool set
  as JSON schemas and requires tool calls as fenced blocks
  `TOOL_CALL: {"name": ..., "arguments": {...}}`; the loop parses, executes,
  appends the result, and continues. Parser tolerates code fences and
  surrounding prose.

Loop: model → tool call(s) → execute under policy → feed results → repeat
until a final text answer or `max_turns`.

## Tools (typical coding-agent union)

`shell` (bounded timeout, capture stdout+stderr+exit), `read_file`,
`write_file`, `edit_file` (unique old→new replace), `list_dir`, `glob`,
`search` (rg if available, else Python grep), `update_plan` (todo list,
surfaced as `plan` items), `web_fetch` (bounded GET, config-enabled).

## Safety

- Git-repo guard: exec refuses outside a git repo (exit 2, message names the
  flag) unless `--skip-git-repo-check`.
- Sandbox (application-level v1): `read-only` denies file writes and
  `shell`; `workspace-write` allows writes inside workdir + `--add-dir`
  roots, shell allowed per policy; `danger-full-access` lifts path guards.
- Approval: interactive prompt in REPL; in exec, denied calls are
  **soft-denied** (notice to stderr naming the tool + how to allow, run
  continues, exit 0 — agy semantics) unless `approval: never` (auto-approve)
  or `--dangerously-bypass-approvals-and-sandbox`.
- Gave-up exit code (C91, ASK DECIDED 2026-09-04; tightened by 91F1): when
  the recovery policy has issued a documented alternative and **the
  advised-against `(tool, error_class)` pair recurs** on a later turn, the run
  stops itself and exec exits **3** (distinct from error 1 and usage 2).
  Stdout carries the honest closing (advisory turn, the pair it was about,
  failed turn, first stuck turn, checkpoint to resume from), and the report
  carries `advised_pair` + `matched_pair` so the closing is checkable.
  The stop is evidence-capped, never turn-count-capped: no advisory ⇒ no stop.
  **91F1:** an unrelated failure after the advisory (a missing path, an empty
  grep) is NOT evidence — an agent that obeys the advisory and switches
  approach must not be stopped, and the original C91 gate armed on any
  post-advisory failure, which made the closing text false.
  A policy stop is not turn exhaustion: it emits no `max_turns` error (91F2).

## Sessions

`~/.codemonkey/sessions/<thread_id>.json` (skipped with `--ephemeral`):
thread_id, provider/model, cwd, messages, created/updated. `resume --last`
and `resume <THREAD_ID>` load history into the run.

## Modular strategy architecture (pluggable, config-selected)

Three domains are interfaces with a registry + config selector, so
strategies can be swapped or added without touching the loop:

```yaml
strategies:
  compaction: summarizing      # summarizing | sliding-window
  memory: file                 # file | none
  session_state: jsonl         # jsonl | sqlite
```

- `codemonkey/strategies/` — `compaction.py`, `memory.py`, `session_state.py`:
  each module defines a base protocol (`compact(messages, budget)`,
  `load/save`, `append/restore`) and a registry mapping config names to
  implementations.
- **Compaction** (applied when history nears the model context limit):
  `summarizing` — call the active provider to summarize older messages into
  a rolling summary block (default); `sliding-window` — keep last N messages
  verbatim, drop the rest (no extra LLM call).
- **Memory** (cross-session, injected into the system prompt):
  `file` — append curated facts to `~/.codemonkey/memory.md` via an
  `update_memory` tool; `none` — disabled.
- **Session state** (persistence backend for sessions):
  `jsonl` — append-only `~/.codemonkey/sessions/<thread_id>.jsonl` (default);
  `sqlite` — `~/.codemonkey/sessions.db` (thread + message tables).
- Unknown strategy names → exit 2 with the list of valid names.
- Adding a strategy later = new class + registry entry + config value.

## Loops 2 & 3 (autonomous, no approval gates)

After loop 1 (cycles 1-9) passes acceptance: a **research cycle** per loop
(web search for best-in-class coding-agent capabilities: e.g. parallel
tool calls, subagents, patch-based editing, checkpoints/rollback,
agentic review, caching, streaming UX, MCP-like extension points) picks the
highest-leverage "10x" improvements, appends them as new cycles to plan.md
(tagged `loop2:` / `loop3:`), and builds them under the same
verify→commit→mark process. User reviews once, after loop 3.

## Acceptance criteria (exact probes; all must pass)

A1. `uv run codemonkey --version` → exit 0, stdout matches `codemonkey x.y.z` (semver).
A2. `uv run codemonkey config` → exit 0; stdout contains `local`, `http://192.168.50.176:8080/v1`, and `Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf`; contains no value matching `sk-`.
A3. `CODEMONKEY_MODEL=override-test uv run codemonkey config` → stdout contains `override-test` (env overrides YAML).
A4. `uv run codemonkey models` → exit 0; stdout contains `Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf` (live server call).
A5. `uv run codemonkey exec "Reply with exactly the word pong and nothing else."` → exit 0; stdout (stderr suppressed) contains `pong`.
A6. `uv run codemonkey exec --json "Reply with exactly the word pong and nothing else."` → exit 0; every stdout line parses as JSON; a line with `"type":"thread.started"` exists and a line with `"type":"turn.completed"` exists.
A7. `echo "Reply with exactly the word banana and nothing else." | uv run codemonkey exec -` → exit 0; stdout contains `banana` (stdin-as-prompt).
A8. `cd $(mktemp -d) && uv run --project ~/Programs/CodeMonkey codemonkey exec --provider local "hi"` → exit 2, stderr mentions git repository and `--skip-git-repo-check` (non-git dir guard).
A9. Tool loop end-to-end (prompt protocol, live model): `cd ~/Programs/CodeMonkey && uv run codemonkey exec --sandbox workspace-write --approval never "Use the shell tool to run: echo codemonkey_tool_test. Then reply with exactly the command output."` → exit 0; stdout contains `codemonkey_tool_test`.
A10. Structured output: `uv run codemonkey exec --output-schema ~/Programs/CodeMonkey/build/schema-repo.json --output-last-message /tmp/cm-repo.json "..."` → exit 0; `/tmp/cm-repo.json` parses as JSON with a non-empty `project_name` string and `programming_languages` string array (schema provided in build/).
A11. Resume: capture `T=$(uv run codemonkey exec --json "Remember the token word: zebra. Reply with ok." | python3 -c 'import sys,json; [print(json.loads(l)["thread_id"]) for l in sys.stdin if l.startswith("{") and "thread.started" in l]')`; then `uv run codemonkey exec resume "$T" "What token word did I give you?"` → exit 0; stdout contains `zebra`.
A12. `uv run codemonkey sessions` → exit 0; the thread id from A11 appears in stdout (non-ephemeral persistence).
A13. `CODEMONKEY_PROVIDER=anthropic uv run codemonkey config` → exit 0; stdout shows provider `anthropic` with `protocol: anthropic` (multi-provider selection; no network call).
A14. Anthropic client unit tests (mock local HTTP server, no network): `uv run pytest tests/test_anthropic.py -q` → exit 0, ≥3 passed.
A15. Full suite: `uv run pytest -q` → exit 0, 0 failed (≥25 tests).
A16. `uv run codemonkey review --uncommitted` (repo with uncommitted changes) → exit 0; stdout ≥ 400 chars (live review run).
A17. Sandbox policy (unit, no LLM): `uv run pytest tests/test_sandbox.py -q` → exit 0; includes a failing-write-assertion test proving `read-only` denies `write_file` and `shell`.
A18. `uv run codemonkey --help` → exit 0; usage section lists `exec`, `review`, `sessions`, `config`, `models`.
A19. Strategy selectors: `strategies.compaction=sliding-window uv run codemonkey config` (or `CODEMONKEY_STRATEGY_COMPACTION=sliding-window` env) → exit 0; stdout shows `sliding-window` as the effective compaction strategy; `codemonkey config` with `strategies: {compaction: bogus}` → exit 2, stderr lists valid names `summarizing` and `sliding-window`.
A20. Session-state backends: unit tests `uv run pytest tests/test_strategies.py -q` → exit 0; includes round-trip tests for BOTH `jsonl` and `sqlite` backends (append then restore yields identical messages) and a `sliding-window` compaction test (old messages dropped, last N kept, no LLM call).

Live-LLM probes (A5, A6, A7, A9, A10, A11, A16) run against
http://192.168.50.176:8080/v1 and are the ground-truth gate for the
prompt-tool-protocol path on the local model.
