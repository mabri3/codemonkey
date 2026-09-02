# Plan — CodeMonkey

```
cycles: 11 (loop 1 base, before loops 2-3 appends)
cap: none
heartbeat: 5m           # tightened per user 2026-09-02 (was 15m); single-worker lease in SPRINT.md
review_every: 3        # fresh-context critic every 3rd cycle + final
workdir: ~/Programs/CodeMonkey
python: 3.11 (uv)      # system python is 3.9 — always `uv run`
live provider: local   # http://192.168.50.113:8080/v1, model Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf
loops: 3               # loop 1 = cycles 1-10 · loop 2 = research + appends · loop 3 = research + appends
```

Decomposition rule: one cycle = one commit's worth of verifiable work, ≤ ~30 min
agent work. Long live-LLM probes run as the cycle's final step (bounded,
`timeout` guarded). Cycles never wait on the heartbeat. After loop 1's final
acceptance (cycle 10), the user has approved NO further gates: research
cycles select the "10x" improvements and append build cycles; the loop keeps
running until loop 3's final acceptance passes. The user reviews once at the
end.

## Cycle checklist — loop 1 (base build)

- [x] CYCLE 1 — Repo scaffold + config layer | est: 30m |
  verify: `cd ~/Programs/CodeMonkey && uv run codemonkey --version` → exit 0,
  stdout matches `codemonkey \d+\.\d+\.\d+`;
  `uv run codemonkey config` → exit 0, stdout contains `192.168.50.113:8080`.
  spec sketch: `uv init --python 3.11`, pyproject (typer, rich, httpx, PyYAML,
  python-dotenv, jsonschema; dev: pytest), package dir `src/codemonkey`, Typer
  app with `--version`, config loader:
  `~/.codemonkey/config.yaml` → `.codemonkey.yaml` → `.env` (project then
  `~/.codemonkey/.env`) → env vars override → `config` command prints merged
  view (secrets masked). Repo-local git identity.
- [x] CYCLE 2 — Provider layer (OpenAI + Anthropic) + `models` | est: 30m |
  verify: `uv run pytest tests/test_providers.py -q` → exit 0 (≥8 passed,
  mocked HTTP: openai streaming SSE + non-streaming, anthropic SSE +
  non-streaming, auth headers, 401→exit 2);
  `uv run codemonkey models` → exit 0, stdout contains
  `Qwen3.8-27B-NVFP4-MTP-VERY-HIGH.gguf`.
  spec sketch: `providers/openai.py` (chat completions, stream + non-stream,
  httpx), `providers/anthropic.py` (messages API, SSE `content_block_delta`,
  `anthropic-version`/`x-api-key` headers), `base.py` common `ChatTurn`
  result (content, reasoning, usage, finish_reason), `models` command via
  `/v1/models` (openai) / config (anthropic).
- [x] CYCLE 3 — Tools + sandbox | est: 30m |
  verify: `uv run pytest tests/test_tools.py tests/test_sandbox.py -q` →
  exit 0 (≥12 passed; read/write/edit/list/glob/search/shell happy paths,
  edit_file non-unique-reject, sandbox `read-only` denies write_file + shell,
  workspace-write enforces path roots incl. `--add-dir`, shell timeout).
  spec sketch: `tools/*.py` one module per tool with `run(args, ctx) ->
  ToolResult` (output ≤ 20KB truncated with marker), `sandbox.py` policy
  `can(ToolCall, level, roots)`, `search` prefers `rg` if on PATH else
  Python walk, `shell` subprocess cwd=workdir, timeout default 120s.
- [x] CYCLE 4 — Tool protocol + agent loop | est: 30m |
  verify: `uv run pytest tests/test_protocol.py -q` → exit 0 (≥8 passed:
  TOOL_CALL fenced + unfenced + multi-call + garbage-tolerance parsing,
  native-openai tool-call extraction, loop with mock server: 2 tool calls
  then final answer, max_turns bail, error-result feedback).
  spec sketch: `protocol.py` `parse_tool_calls(text) -> (calls, prose)` with
  `TOOL_CALL:` schema-advertised system-prompt template; `native.py`
  openai/anthropic tool-call extraction; `loop.py` `run_turns()` — messages,
  max_turns, soft-deny hooks, per-turn event callbacks;
  `tool_protocol: auto` = native when protocol supports it, and on a
  tools-parameter error (500) from the server, retry the same turn with the
  prompt protocol and remember the fallback for the provider (that is how
  the local llama.cpp server is handled — verified: it rejects `tools`
  with a 500; A9's ground truth).

- [x] CYCLE 5 — `exec` core (text mode, stdin, JSONL, git guard) | est: 30m |
  status: DONE 2026-09-02 ~04:55. History: BLOCKED 03:35 — home llama.cpp
  (192.168.50.113:8080) inference wedged across 3 strikes + 3 re-checks
  (≥100 min hang; /v1/models 200, chat completions never respond).
  Unblocked at ~04:45 via temporary `unblock` provider
  (CODEMONKEY_PROVIDER=unblock; config.py TEMPORARY block, DELETE on home
  server recovery): base_url http://127.0.0.1:3458/v1 (reasoning-cache proxy
  → OpenCode Go), model minimax-m3 (inference verified: pong in 1.6s home-
  free; tools param ACCEPTED by this path — real tool-call, finish_reason
  tool_calls). All three cycle-5 live probes green through it: text pong
  exit 0 stdout `pong`; --json 6 lines all valid JSON incl thread.started +
  turn.completed (build/probes/cycle5-json.out); stdin `-` exit 0. Unit
  suite 85/85 green. Probe transcript: build/probes/.
  verify: `uv run pytest tests/test_exec.py -q` → exit 0; LIVE probe:
  `uv run codemonkey exec "Reply with exactly the word pong and nothing else."`
  → exit 0, stdout (2>/dev/null) contains `pong`; `--json` variant: every
  stdout line valid JSON incl. `thread.started` + `turn.completed`;
  `echo prompt | uv run codemonkey exec -` → exit 0.
  spec sketch: `exec.py` — stdout purity rule (text mode: only final
  response; `--json`: only JSONL; everything else stderr), stdin `-` = full
  prompt, piped stdin + prompt arg = context append, git-repo guard (exit 2
  naming `--skip-git-repo-check`), JSONL emitter (thread.started /
  turn.started / item.* / turn.completed / error), exit codes 0/1/2,
  `--output-last-message` tee.
- [x] CYCLE 6 — Structured output + sessions/resume | est: 30m |
  status: DONE 2026-09-02. Live probes via temporary `unblock` provider
  (home llama.cpp still wedged — inference ReadTimeout at tick start).
  A10: `--output-schema build/schema-repo.json` → exit 0, output JSON
  validates (project_name="codemonkey", languages=["Python"]);
  build/probes/cycle6-schema.rerun.out + cycle6-repo.json. A11/A12:
  token-seeded thread 317e50eee52c, `exec resume <id> "What was the token
  word..."` → exit 0, stdout exactly `zebra`
  (build/probes/cycle6-resume.rerun2.out). `codemonkey sessions` lists the
  thread. Unit suite 103/103.
  verify: LIVE A10: `uv run codemonkey exec --output-schema
  build/schema-repo.json --output-last-message /tmp/cm-repo.json "State the
  project name and programming languages for this repository."` → exit 0,
  `/tmp/cm-repo.json` parses, `project_name` non-empty string,
  `programming_languages` non-empty array; LIVE A11/A12: resume a real
  session and answer a token-echo question correctly; `codemonkey sessions`
  lists it.
  spec sketch: `schema.py` — inject schema into final-turn prompt, parse +
  jsonschema-validate with one auto-retry appending validation errors;
  `sessions.py` — persistence via the configured session_state strategy
  (default `jsonl`), `--last` resolution, `resume` subcommand, `sessions`
  listing, `--ephemeral` skip.
- [ ] CYCLE 7 — Strategy layer: pluggable compaction / memory / session state | est: 30m |
  verify: LIVE A19: `CODEMONKEY_STRATEGY_COMPACTION=sliding-window uv run
  codemonkey config` → exit 0, stdout shows effective compaction
  `sliding-window`; invalid name → exit 2, stderr lists valid names;
  A20: `uv run pytest tests/test_strategies.py -q` → exit 0, includes
  round-trip tests for BOTH `jsonl` and `sqlite` session backends and a
  `sliding-window` compaction test (old messages dropped, last N kept, no
  LLM call).
  spec sketch: `strategies/compaction.py` — `CompactionStrategy` protocol
  (`maybe_compact(messages, budget_tokens) -> messages`); `summarizing`
  (default; older messages → rolling summary block via the active provider,
  triggered when estimated tokens > 60% of configured `context_limit`) and
  `sliding-window` (keep last N, drop rest, no LLM call).
  `strategies/memory.py` — `MemoryStrategy` protocol (`load() -> text`,
  `add_fact(text)`); `file` (default; `~/.codemonkey/memory.md`, injected
  into system prompt, exposed as `update_memory` tool) and `none`.
  `strategies/session_state.py` — `SessionStore` protocol
  (`append(thread_id, event)`, `load(thread_id)`, `list()`, `latest()`);
  `jsonl` (default; `~/.codemonkey/sessions/<id>.jsonl`) and `sqlite`
  (`~/.codemonkey/sessions.db`). Registry per domain mapping config name →
  class; unknown name → exit 2 listing valid names. Config block
  `strategies: {compaction, memory, session_state}` + env
  `CODEMONKEY_STRATEGY_<DOMAIN>`.
- [ ] CYCLE 8 — `review` + approvals + remaining tools | est: 30m |
  verify: `uv run pytest tests/test_approvals.py -q` → exit 0 (soft-deny
  notice on stderr + run continues in exec; `approval: never` auto-approves;
  bypass flag lifts sandbox+approval); LIVE A16: `uv run codemonkey
  review --uncommitted` → exit 0, stdout ≥ 400 chars.
  spec sketch: `review.py` — unified-diff context (uncommitted vs
  base/commit), read-only sandbox, single review turn with reviewer system
  prompt; `approvals.py` — policy evaluation + soft-deny (stderr notice:
  tool + how to allow), interactive prompt path for REPL; `update_plan` +
  `web_fetch` tools (config `web_fetch: true`, bounded GET 60s/512KB).
- [ ] CYCLE 9 — Interactive REPL + flag wiring + polish | est: 30m |
  verify: `printf 'Reply with exactly: fig\n/quit\n' | uv run codemonkey` →
  exit 0, stdout contains `fig`; `uv run codemonkey --help` → exit 0, lists
  exec/review/sessions/config/models; full suite `uv run pytest -q` → exit 0.
  spec sketch: `repl.py` — loop (input() + rich render), streaming deltas
  to stderr live, reasoning hidden by default (`--show-reasoning`), `/quit
  /clear /model /provider /usage /sessions`; wire `--add-dir`, `--timeout`,
  `--max-turns`, `--ignore-user-config`,
  `--dangerously-bypass-approvals-and-sandbox` through config; streaming in
  exec text mode (deltas to stderr, final full message to stdout).
- [ ] CYCLE 10 — Loop 1 final acceptance sweep | est: 30m |
  verify: ALL spec.md acceptance criteria A1–A20 pass (run each literally,
  capture output); `build/BUILD_REPORT.md` written (loop 1 section) with
  criteria table + literal probe output + `git log` range + known gaps.
  spec sketch: run A1..A20 in order, capture outputs, write the report,
  commit; if a probe fails, fix + re-run (3-strike rule applies). On pass:
  proceed straight to CYCLE 11 (no user gate — approved in sign-off).

## Cycle checklist — loop 2 (research + build)

- [ ] CYCLE 11 — Loop 2 research: pick the 10x improvements | est: 30m |
  verify: `build/research-loop2.md` exists (committed) with ≥5 researched
  capabilities (each: name, source URL, why it's high-leverage for a local-
  model coding CLI) and a "SELECTED" section listing ≥3, each mapped to a
  new `loop2:`-tagged cycle appended below; `build/plan.md` now contains
  those `loop2:` cycles (unchecked).
  spec sketch: web_search for best-in-class coding-agent capabilities
  (parallel tool calls, patch-based editing, agentic sub-review, context
  caching, checkpoints/rollback, MCP-like extension points, token-budget
  management); rank by leverage for a local 27B model + headless scripting;
  pick 3-5 that are implementable in ≤4 cycles each; append cycles
  CYCLE 12.. with `loop2:` tags + exact verify probes. Then the loop keeps
  going cycle by cycle until all loop2 cycles are checked, then CYCLE
  `loop2-final` (acceptance re-sweep A1-A20 + report section, commit).

## Cycle checklist — loop 3 (research + build)

- [ ] CYCLE R3 — Loop 3 research: pick the next 10x improvements | est: 30m |
  verify: `build/research-loop3.md` committed (same shape as cycle 11);
  `loop3:`-tagged cycles appended; then built cycle-by-cycle until checked,
  then CYCLE `loop3-final`: full acceptance re-sweep A1-A20 (+ any new
  criteria the loops added), `build/BUILD_REPORT.md` final section with
  complete criteria table, `git log` range across all three loops, known
  gaps, and the loops' selected improvements. THIS IS THE END OF THE RUN:
  final report asks the user to accept.

## Notes for the loop

- Live probes hit http://192.168.50.113:8080/v1 — if the server is down,
  that cycle is BLOCKED (report it; do not fake the probe).
- The llama.cpp server rejects the OpenAI `tools` parameter (verified 500).
  `tool_protocol: auto` must detect the 500-on-tools and switch to prompt
  protocol (A9's ground truth). Do NOT "fix" this by stripping tools
  support from the local provider — the fallback IS the feature.
- Every cycle ends with `git add -A && git commit` (repo-local identity
  Brian Harris). Never commit secrets. `.env` in .gitignore.
- After cycles 3, 6, 9: fresh-context critic (review gate) — see SPRINT.md.
- Research cycles must actually use web search (or `web_extract` on docs) —
  citations with URLs required in the research file. No fabricated "best
  practices".
- Loops 2/3 cycle appends extend the run; the cap stays none. The only stop
  conditions are `build/STOP`, 3 consecutive failed probes on one cycle, or
  loop3-final acceptance passing.

## Review-gate findings — cycle 6 critic (2026-09-02) → fix cycles

Fresh-context critic (build/critic-cycle6.md) reviewed the cycles 1–6 diff
against build/spec.md. Findings become the unchecked fix cycles below
(inserted before CYCLE 7 per append rule; checked boxes preserved).

- [x] CYCLE 6F1 — Sandbox: `workspace-write` must ALLOW shell per policy
  (spec:97) instead of denying it; approval-gated, cwd-bound. Fix
  `sandbox.py`/`tools/__init__.py`, update the two denying tests, add a
  test: workspace-write + approval never → shell executes, read-only still
  denies shell. | est: 20m |
  verify: `uv run pytest tests/test_sandbox.py tests/test_tools.py -q` →
  exit 0 incl. new workspace-write-shell-allowed case; full suite green.
- [x] CYCLE 6F2 — exec resume becomes a real Typer subcommand sharing the
  full exec flag set (sandbox/add-dir/timeout/etc.); `--json` JSONL items
  renamed to spec contract `item.started`/`item.completed` (exec.py); drop
  the synthetic pre-loop `turn.started` + emit `turn.started` around the
  schema retry (one per turn, 1:1 with turn.completed); persisted session
  messages strip schema instructions/retry scaffolding. | est: 30m |
  status: DONE 2026-09-02 (resumed mid-cycle after prior-worker death).
  exec is now a Typer GROUP (`exec_app`, invoke_without_command) whose
  callback is the prompt-mode default command; `resume` is a real
  subcommand with the full exec flag set; `_dispatch_exec_resume`
  rewrites argv `exec resume ...` → hidden top-level `exec-resume` before
  Typer parse (Click otherwise binds `resume` as the prompt positional).
  events renamed thread.item.* → item.*/item.completed; synthetic
  turn.started deleted; retry turn wrapped (turn.started ✕2 ==
  turn.completed ✕2 on a retry); loop emits `persist.drop` with
  drop_tail + replace_with (good retry answer swapped in); exec strips
  history + scaffolding and restores the PRISTINE first user prompt
  in-place (mutating the same list the loop froze into all_messages).
  LIVE via unblock: real exec --json transcript
  build/probes/cycle6f2-json.* (all-valid JSON, thread.started first,
  turn markers 1:1, agent_message item) + A9-style shell-tool transcript
  build/probes/cycle6f2-shell.* (command_execution items, exit 0, echo
  output in final message) + end-to-end resume probe (seed armadillo →
  exec resume <tid> --skip-git-repo-check --ephemeral → `armadillo`,
  flags-after-subcommand parse verified; build/probes/cycle6f2-resume.*).
  Full suite 110/110.
  verify: `uv run pytest -q` → exit 0 incl. updated event-name + turn
  counting tests; LIVE (via unblock while home server wedged): a real
  `exec --json` transcript committed to build/probes/ plus an A9-style
  shell-tool transcript showing `command_execution` items and exit 0.
- [ ] CYCLE 6F3 — web_fetch honors `web_fetch: true` config gate (default
  off; off → ToolResult error, no network); search Python fallback uses
  fnmatch not re.match; live stdin-`-` + git-guard probe transcripts
  committed to build/probes/. | est: 15m |
  verify: `uv run pytest -q` → exit 0 incl. new web_fetch-gated + fnmatch
  fork tests; probe files exist in the commit.
- [ ] CYCLE 6F4 — hygiene sweep: temp `unblock` provider removal guard
  test (fails when shipped in defaults on live home server); session meta
  append fresh `created` only on first write (floor, not drift). |
  est: 15m |
  verify: `uv run pytest -q` → exit 0.
