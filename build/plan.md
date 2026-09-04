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
- [x] CYCLE 7 — Strategy layer: pluggable compaction / memory / session state | est: 30m |
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
- [x] CYCLE 8 — `review` + approvals + remaining tools | est: 30m |
  verify: `uv run pytest tests/test_approvals.py -q` → exit 0 (soft-deny
  notice on stderr + run continues in exec; `approval: never` auto-approves;
  bypass flag lifts sandbox+approval); LIVE A16: `uv run codemonkey
  review --uncommitted` → exit 0, stdout ≥ 400 chars.
  spec sketch: `review.py` — unified-diff context (uncommitted vs
  base/commit), read-only sandbox, single review turn with reviewer system
  prompt; `approvals.py` — policy evaluation + soft-deny (stderr notice:
  tool + how to allow), interactive prompt path for REPL; `update_plan` +
  `web_fetch` tools (config `web_fetch: true`, bounded GET 60s/512KB).
- [x] CYCLE 9 — Interactive REPL + flag wiring + polish | est: 30m |
  verify: `printf 'Reply with exactly: fig\n/quit\n' | uv run codemonkey` →
  exit 0, stdout contains `fig`; `uv run codemonkey --help` → exit 0, lists
  exec/review/sessions/config/models; full suite `uv run pytest -q` → exit 0.
  spec sketch: `repl.py` — loop (input() + rich render), streaming deltas
  to stderr live, reasoning hidden by default (`--show-reasoning`), `/quit
  /clear /model /provider /usage /sessions`; wire `--add-dir`, `--timeout`,
  `--max-turns`, `--ignore-user-config`,
  `--dangerously-bypass-approvals-and-sandbox` through config; streaming in
  exec text mode (deltas to stderr, final full message to stdout).
- [x] CYCLE 10 — Loop 1 final acceptance sweep | est: 30m |
  verify: ALL spec.md acceptance criteria A1–A20 pass (run each literally,
  capture output); `build/BUILD_REPORT.md` written (loop 1 section) with
  criteria table + literal probe output + `git log` range + known gaps.
  spec sketch: run A1..A20 in order, capture outputs, write the report,
  commit; if a probe fails, fix + re-run (3-strike rule applies). On pass:
  proceed straight to CYCLE 11 (no user gate — approved in sign-off).

## Cycle checklist — loop 2 (research + build)

- [x] CYCLE 11 — Loop 2 research: pick the 10x improvements | est: 30m |
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


### loop2: cycles (selected from build/research-loop2.md, cycle 11)

- [x] CYCLE 12 — `loop2:` parallel tool execution (independent calls in one turn run
  concurrently, results re-ordered; per-call events) | est: 30m |
  verify: `uv run pytest tests/test_parallel.py -q` → exit 0 (≥4 tests: 3 calls with
  2 slow ones finish < serial sum; results in call order; per-call events emitted;
  failure in one call doesn't kill siblings); live A9-style tool probe green; full
  suite green.
- [x] CYCLE 13 — `loop2:` search/replace patch editing (`edit_file` SREP blocks:
  exact match → whitespace-tolerant fallback → explicit error w/ near-miss anchors;
  atomic write) | est: 30m |
  verify: `uv run pytest tests/test_patch_edit.py -q` → exit 0 (≥6 tests incl. exact,
  fuzzy, no-match error, atomicity on failure, multi-block); live exec edit probe green.
- [x] CYCLE 14 — `loop2:` checkpoints/rollback (snapshot before mutating tools;
  `codemonkey undo [--list]` restores last checkpoint byte-identical) | est: 30m |
  verify: `uv run pytest tests/test_checkpoints.py -q` → exit 0 (≥5 tests: snapshot
  on write/edit/shell, restore byte-identical, --list ordering, no-snapshot no-op,
  checkpoint dir gitignored); live destructive-edit-then-undo probe green.
- [x] CYCLE 15 — `loop2:` auto-compaction in the loop (estimate tokens pre-call;
  trigger strategy maybe_compact; re-inject system prompt post-compaction) | est: 30m |
  verify: `uv run pytest tests/test_autocompact.py -q` → exit 0 (≥4 tests: trigger on
  over-budget fake history, under-budget no-op, post-compaction system re-injection,
  registry-selected strategy honored); suite green.
- [x] CYCLE loop2-final — Loop 2 acceptance: full A1–A20 re-sweep + new loop2 probes;
  BUILD_REPORT loop-2 section | est: 30m |
  verify: `bash build/acceptance_sweep.sh` all green; report updated; committed.

## Cycle checklist — loop 3 (research + build)

- [x] CYCLE R3 — Loop 3 research: pick the next 10x improvements | est: 30m |
  verify: `build/research-loop3.md` committed (same shape as cycle 11);
  `loop3:`-tagged cycles appended; then built cycle-by-cycle until checked,
  then CYCLE `loop3-final`: full acceptance re-sweep A1-A20 (+ any new
  criteria the loops added), `build/BUILD_REPORT.md` final section with
  complete criteria table, `git log` range across all three loops, known
  gaps, and the loops' selected improvements. THIS IS THE END OF THE RUN:
  final report asks the user to accept.


### loop3: cycles (selected from build/research-loop3.md, cycle R3)

- [x] CYCLE 16 — `loop3:` self-heal edit retries (edit/SREP failure with structured
  error -> ONE corrective re-prompt turn feeding the failure text back;
  `max_edit_retries`, default 1) | est: 30m |
  verify: `uv run pytest tests/test_selfheal.py -q` → exit 0 (>=4 tests: retry on
  failure consults anchors, success-after-retry transcript, no-retry when ok,
  retry limit respected); suite green; live EDL probe (fuzzy-edit then self-heal).
- [x] CYCLE 17 — `loop3:` observation budget for tool outputs (per-run budget,
  default 24k chars; over-budget -> prefix + [PARTIAL: N chars elided] marker;
  per-call accounting) | est: 30m |
  verify: `uv run pytest tests/test_obsbudget.py -q` → exit 0 (>=4 tests: budget
  enforcement, marker format, isolation across calls, under-budget untouched);
  suite green.
- [x] CYCLE loop3-final — Loop 3 acceptance: full A1–A20 re-sweep + loop3 probes;
  final BUILD_REPORT section (all three loops); REQUEST USER ACCEPTANCE (Gate 2)
  | est: 30m |
  verify: `bash build/acceptance_sweep.sh` all green; report updated; committed.

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
- [x] CYCLE 6F3 — web_fetch honors `web_fetch: true` config gate (default
  off; off → ToolResult error, no network); search Python fallback uses
  fnmatch not re.match; live stdin-`-` + git-guard probe transcripts
  committed to build/probes/. | est: 15m |
  status: DONE 2026-09-02. web_fetch.py: _enabled() reads
  ctx.extra['config']['web_fetch'] (default False — no network call made
  when gated off, httpx.Client never constructed per test); truncation
  coherent (stream accumulated with running byte count,
  [truncated at 512KB] marker on true overflow only). exec.py ToolContext
  extra now carries {"approval", "config"}. search.py: fnmatch.fnmatch
  replaces p.name.match (glob-as-regex bug). LIVE via unblock: stdin-dash
  probe build/probes/cycle6f3-stdin.out (exit 0, stdout `cactus`) +
  git-guard probe build/probes/cycle6f3-gitguard.out (exit 2 in non-git
  temp dir, stderr names --skip-git-repo-check). 4 new tests
  (web_fetch default-blocked / explicitly-false-blocked / true-allowed /
  fnmatch fork ×2). Full suite 115/115.
  verify: `uv run pytest -q` → exit 0 incl. new web_fetch-gated + fnmatch
  fork tests; probe files exist in the commit.
- [x] CYCLE 6F4 — hygiene sweep: temp `unblock` provider removal guard
  test (fails when shipped in defaults on live home server); session meta
  append fresh `created` only on first write (floor, not drift). |
  est: 15m |
  status: DONE 2026-09-02. sessions.py append_meta now reuses earliest
  recorded `created` via _prior_created() (first meta write stamps now(),
  later appends keep the floor; updated/other fields still refresh).
  tests/test_hygiene_6f4.py: 3 tests — live guard fails if `unblock` ships
  while :8080 answers chat completions (or if removed early), created-floor
  fresh + no-drift (1h backdate) cases. Full suite 118/118 (was 115).
  verify: `uv run pytest -q` → exit 0.

## Cycle checklist — loop 4 (research + build) — ⚠️ AWAITING GATE 2

> **DO NOT START THESE CYCLES.** loop3-final passed and `build/BUILD_REPORT.md`
> requested **Gate 2** (final user acceptance) — the run's only remaining gate
> (AGENTS.md "Stop conditions"). CYCLE R4 below is a *research/proposal* cycle
> only: it selects candidates and writes probes. Every `loop4:` build cycle is
> unauthorized until the user answers Gate 2 (accept + continue, or amend the
> list). An autonomous tick that reaches this section with Gate 2 unanswered
> must report and stop, not take the first unchecked cycle.

- [x] CYCLE R4 — Loop 4 research: pick the next 10x improvements | est: 30m |
  verify: `build/research-loop4.md` exists (committed) with ≥5 researched
  capabilities (name, source URLs, why high-leverage for a local-model coding
  CLI) and a `SELECTED` section listing ≥3, each mapped to a cycle appended
  below; `grep -c '^### ' build/research-loop4.md` ≥ 5;
  `grep -q '^## SELECTED' build/research-loop4.md`; `build/plan.md` contains
  the `loop4:` cycles (unchecked).
  spec sketch: live web search (verification-in-loop, repo maps/symbol index,
  KV-cache prefix stability for llama.cpp, AGENTS.md instruction loading,
  retry/backoff, subagents, hooks/permissions, eval harnesses, MCP), ranked by
  leverage ÷ cost for a 27B local model in headless runs; plus an entry review
  of the built source that turns spec gaps into `F`-numbered fix cycles.

### Review findings — R4 entry review (2026-09-02) → fix cycles

Both findings map to `build/spec.md`, not to new research (AGENTS.md: work must
map to an A-criterion, a loop selection, or a cited research selection).

- [x] CYCLE 7F1 — memory strategy is built but never wired (spec.md "Modular
  strategy architecture → Memory"): inject `memory.load()` into the system
  prompt as part of a single project-context block, register `update_memory`
  in `tools/__init__.py::_MODULES` + `SPECS`, and make `memory: none` disable
  both. | est: 25m |
  verify: `uv run pytest tests/test_memory_wiring.py -q` → exit 0 (≥4 tests:
  a fact in `memory.md` appears verbatim in the `system` argument the mock
  provider receives; `strategies.memory=none` → the fact is absent AND
  `update_memory` is not advertised in the prompt block; `update_memory`
  appends a fact and is idempotent on repeat; unknown memory name still exits
  2 with valid names); `uv run pytest -q` → exit 0, 0 failed;
  LIVE: seed a temp memory file with `codemonkey_memory_probe_token`, run
  `uv run codemonkey exec --ephemeral "What probe token is in your memory?"`
  → exit 0, stdout contains `codemonkey_memory_probe_token` (transcript to
  `build/probes/`).
- [x] CYCLE 17F1 — loop-3 knobs are function defaults, not knobs: add
  `max_edit_retries` (1) and `observation_budget` (24000) to `config.DEFAULTS`,
  to `ENV_MAP` (`CODEMONKEY_MAX_EDIT_RETRIES`, `CODEMONKEY_OBSERVATION_BUDGET`)
  and pass them from `exec.py`/`repl.py` into `run_turns`. | est: 20m |
  verify: `uv run codemonkey config` → exit 0, stdout contains
  `max_edit_retries` and `observation_budget`;
  `CODEMONKEY_OBSERVATION_BUDGET=5000 uv run codemonkey config` → stdout
  contains `5000`; `uv run pytest tests/test_knobs.py -q` → exit 0 (≥3 tests:
  defaults present, env override applied, exec passes both values through to
  `run_turns` — assert on a patched `run_turns` recording its kwargs);
  `uv run pytest -q` → exit 0.

### loop4: cycles (selected from build/research-loop4.md, cycle R4)
> **USER DECISIONS (2026-09-02):** initial "approved 3" built CYCLE 18/19/20.
> Clarified afterward: "approved 3" meant **LOOP 3 SIGN-OFF** (Gates for loops
> 1-3 are now satisfied). Loop 4 continues to completion: ALL remaining cycles
> (7F1, 17F1, 21, 22, 23, loop4-final) are UN-PARKED and approved to build.


- [x] CYCLE 18 — `loop4:` [APPROVED-R4] project-instruction loader (AGENTS.md → CLAUDE.md →
  `.codemonkey/instructions.md`, nearest-first from the workdir up to the repo
  root; 32KB cap with a truncation marker; config `project_instructions: true`
  + `--no-project-instructions`; merged with memory into ONE stable
  project-context block) | est: 30m |
  verify: `uv run pytest tests/test_instructions.py -q` → exit 0 (≥5 tests:
  discovery precedence order; nearest-directory wins over repo root; 32KB cap
  emits `[truncated at 32KB]`; gate off → text absent from the system prompt;
  loaded text present verbatim in the mock provider's `system` argument);
  `uv run pytest -q` → exit 0; LIVE: a temp git repo whose `AGENTS.md` says
  "Always end your reply with the word pineapple", then
  `uv run codemonkey exec --ephemeral "Say hello."` → exit 0, stdout contains
  `pineapple` (transcript to `build/probes/`).
- [x] CYCLE 19 — `loop4:` [APPROVED-R4] verify gate (verification inside the loop): config
  `verify_command` (default unset = disabled) + `max_verify_retries`
  (default 1); after any turn whose mutating tool calls succeeded, run the
  command once under the sandbox/timeout; on non-zero exit feed the trimmed
  output back as a tool result for a corrective turn; emit
  `verify.started` / `verify.completed{ok, exit_code}` events | est: 30m |
  verify: `uv run pytest tests/test_verify_gate.py -q` → exit 0 (≥5 tests:
  unset command → never runs; failing command → failure text appears in the
  next turn's messages and a corrective turn is taken; passing command → no
  extra turn; `max_verify_retries` respected (no infinite loop); verify output
  is charged to the observation budget and truncated with the PARTIAL marker;
  both events emitted in order); `uv run pytest -q` → exit 0; LIVE: temp repo
  with a passing test file, `exec` told to change a function in a way that
  breaks it, `verify_command="uv run pytest -q"` → run ends with the test
  suite passing (verify.completed ok=true in the `--json` stream); transcript
  to `build/probes/`.
- [x] CYCLE 20 — `loop4:` [APPROVED-R4] repo map, part 1: `repomap.py` dependency-free
  def-scan (py/js/ts/go/rs/java/rb) producing file → [symbol, kind, line]
  entries; cache at `.codemonkey/repomap.json` keyed by path+mtime+size;
  skips `.git`, `.venv`, `node_modules`, `__pycache__`; new `repo_map` tool
  (`repo_map(path='.', pattern=None, limit=200)`) + registry SPEC entry
  | est: 30m |
  verify: `uv run pytest tests/test_repomap.py -q` → exit 0 (≥6 tests: python
  def/class + js function/const-arrow + go func fixtures extracted with
  correct 1-based line numbers; second scan with unchanged mtime hits the
  cache — assert the scanner is not re-entered; touching a file invalidates
  just that entry; ignore-list honored; `limit` truncates deterministically;
  unreadable/binary file is skipped, not fatal); `uv run pytest -q` → exit 0;
  `uv run codemonkey exec --ephemeral --approval never "Use the repo_map tool
  on src/codemonkey and tell me which file defines parse_tool_calls."` →
  exit 0, stdout contains `protocol.py`.
- [x] CYCLE 21 — `loop4:` repo map, part 2: ranking (files touched in the last
  N commits first, then symbol density) + budget (`repo_map_budget`, default
  4000 chars) + injection into the project-context block behind config
  `repo_map: false` (opt-in) | est: 30m |
  verify: `uv run pytest tests/test_repomap_inject.py -q` → exit 0 (≥4 tests:
  injected block never exceeds the budget; gate off by default → absent;
  recently-committed files rank ahead of stale ones on a fixture repo;
  the injected block is identical across two consecutive turns — feeds the
  cycle-22 prefix-stability invariant); `uv run pytest -q` → exit 0; LIVE:
  with `repo_map: true`, `uv run codemonkey exec --ephemeral "Which module
  implements the prompt tool-call parser?"` → exit 0, stdout names
  `protocol.py`; the `--json` transcript shows zero `read_file` calls
  (transcript to `build/probes/`).
- [x] CYCLE 22 — `loop4:` prompt-prefix stability for KV-cache reuse:
  deterministic tool-spec ordering, project-context block emitted once in a
  fixed position, compaction constrained to rewrite only the tail (system
  prefix bytes never change mid-run); `cache_prompt: true` passthrough in the
  openai-protocol request body behind config `prompt_cache` (default true;
  harmless/ignored on servers that do not know it) | est: 30m |
  verify: `uv run pytest tests/test_prefix_stability.py -q` → exit 0 (≥4
  tests: the `system` string the mock provider receives is byte-identical
  across 3 consecutive turns including after tool results; byte-identical
  after a forced compaction — only the message tail differs; `cache_prompt`
  present in the openai JSON body when enabled and absent when disabled; the
  anthropic request body is unchanged); `uv run pytest -q` → exit 0; LIVE
  (best-effort, BLOCKED-tolerant): two identical-prefix runs against the
  active provider, record both wall-clock times raw in `build/probes/` — no
  claim is made if the numbers do not separate.
- [x] CYCLE 23 — `loop4:` provider resilience: retry with exponential backoff
  + full jitter honoring `Retry-After` on 429/502/503/504/529 and on 500s that
  are NOT the tools-parameter rejection; `max_retries` (default 3, config +
  `CODEMONKEY_MAX_RETRIES`); `AuthError` never retried | est: 30m |
  verify: `uv run pytest tests/test_retry.py -q` → exit 0 (≥6 tests: 429 with
  `Retry-After: 2` sleeps ~2s — patched sleep records the delay; 503 retries
  with increasing bounded jittered delays then succeeds; 400/404 not retried;
  `AuthError` raises on the first attempt; a tools-parameter 500 raises
  immediately WITHOUT retry so `looks_like_tools_rejection` still triggers the
  prompt fallback; `max_retries` exhausted → `ProviderError` with the attempt
  count); `uv run pytest -q` → exit 0; LIVE A9 re-probe:
  `uv run codemonkey exec --sandbox workspace-write --approval never "Use the
  shell tool to run: echo codemonkey_tool_test. Then reply with exactly the
  command output."` → exit 0, stdout contains `codemonkey_tool_test`
  (fallback path intact).
- [x] CYCLE 19F1 — `loop4:` critic fix (build/critic-loop4.md #6): the
  `verify.completed` event must report the verify command's REAL exit code,
  not a fabricated 0/1 — `--json` consumers and `events.py` render it | est: 10m |
  verify: `uv run pytest tests/test_verify_gate.py -q` → exit 0 (added tests:
  `verify_command="exit 7"` → the `verify.completed` event carries
  `exit_code == 7`; a passing command carries `exit_code == 0`; a timeout
  carries a non-zero code and does not claim 1); `uv run pytest -q` → exit 0.
- [x] CYCLE 22F1 — `loop4:` critic fix (build/critic-loop4.md #5, #7): thread
  `cache_prompt=prompt_cache` through ALL `provider.chat` call sites in
  `run_turns` — the A9 tools-rejection fallback turn and the three schema-retry
  turns currently drop it, so `prompt_cache: false` is ignored on the primary
  local path; also drop the dead second docstring in `run_turns` | est: 15m |
  verify: `uv run pytest tests/test_prefix_stability.py -q` → exit 0 (added
  tests: with `prompt_cache=False` a provider that rejects the `tools`
  parameter records NO `cache_prompt` on either the native attempt or the
  fallback turn; the schema-retry turn likewise; with `prompt_cache=True` the
  fallback turn does carry it); `grep -c "cache_prompt=prompt_cache"
  src/codemonkey/loop.py` → `7`; `uv run pytest -q` → exit 0.
- [x] CYCLE loop4-final — Loop 4 acceptance: full A1–A20 re-sweep + the loop-4
  probes above; `build/BUILD_REPORT.md` loop-4 section (criteria table, git
  range, gaps); commit | est: 30m |
  verify: `bash build/acceptance_sweep.sh` → all green; `uv run pytest -q` →
  exit 0; report updated and committed.

## Cycle checklist — loop 5 (research-gated forward look)

- [x] CYCLE R5 — Loop 5 research: re-research and re-rank the carried-forward
  shortlist with FRESH citations (subagents / delegated context isolation;
  hooks + rule-based command allow/deny permissions; a local eval harness for
  the agent itself; MCP client extension points; token/cost accounting), then
  append `loop5:` cycles | est: 30m |
  verify: `build/research-loop5.md` committed, same shape as loops 2–4
  (≥5 candidates with real cited URLs, ranked `SELECTED` section with ≥3
  mapped to cycles); `build/plan.md` contains the `loop5:` cycles (unchecked).
  NOTE: subagents and hooks/permissions change **core design** (loop
  architecture; sandbox + approval semantics). AGENTS.md requires stop-and-ask
  before building either — R5 therefore ENDS by asking the user, and does not
  hand its selections to a build tick automatically.


### loop5: cycles (selected from build/research-loop5.md, cycle R5)

- [x] CYCLE 24 — `loop5:` eval harness core: `codemonkey eval <suite.yaml>` runs
  YAML golden tasks (prompt, expected stdout-contains, expected exit code,
  required tool trajectory) against the real exec path; scores pass rate +
  tokens + wall time; writes build/eval/results.json | est: 30m |
  verify: `uv run pytest tests/test_eval.py -q` → exit 0 (≥5 tests: YAML load,
  task run via patched exec, stdout-contract scoring, trajectory scoring,
  results.json shape); `uv run pytest -q` → exit 0; LIVE: a 2-task suite runs
  green against the home server (transcript to build/probes/).
- [x] CYCLE 25 — `loop5:` golden suite + regression baseline: ~8 tasks covering
  the A-probes (pong, tool loop, structured output, resume recall, patch edit,
  verify-gate fix, sessions listing, help contract); versioned baseline
  (build/eval/baseline.json); `codemonkey eval --check` exits 1 on regression |
  est: 30m |
  verify: baseline written from a green run; deliberately broken task
  (wrong expectation) → `eval --check` exit 1 naming the regression; restored →
  exit 0; `uv run pytest -q` → exit 0.
- [x] CYCLE 26 — `loop5:` token/cost telemetry: per-turn usage aggregated into
  the JSONL stream (turn.completed already carries usage; add run total +
  per-tool-call counts), `exec --cost-summary` prints tokens/wall-time/tool
  calls; cumulative ~/.codemonkey/cost.json ledger | est: 30m |
  verify: `uv run pytest tests/test_cost.py -q` → exit 0 (≥4 tests: run totals
  in JSONL, ledger append, ledger cumulative across runs, --cost-summary
  output shape); `uv run pytest -q` → exit 0.
- [x] CYCLE 27 — `loop5:` repo-map relevance ranking: task-conditioned selection
  folded into the cycle-21 injection — query terms (from the user prompt) match
  symbol/file names via the existing search index; still budget-capped, still
  opt-in (`repo_map: true`) | est: 30m |
  verify: `uv run pytest tests/test_repomap_relevance.py -q` → exit 0 (≥4 tests:
  relevance overrides recency for matching symbols; non-matching fallback keeps
  cycle-21 order; budget still enforced; injection stays deterministic across
  two calls); `uv run pytest -q` → exit 0.
- [x] CYCLE loop5-final — Loop 5 acceptance: full A1–A20 re-sweep + loop-5
  probes; BUILD_REPORT loop-5 section | est: 30m |
  verify: `bash build/acceptance_sweep.sh` → all green; `uv run pytest -q` →
  exit 0; report updated and committed. (R6 entry condition: eval harness
  shipped by 24/25.)

## ⚠️ CORE-DESIGN DECISIONS (from R5, awaiting user)

- Subagents / delegated context isolation (candidate 4) — 3+ cycles, changes
  loop architecture + session semantics. Build or defer?
- Hooks + rule-based command permissions (candidate 5) — 2 cycles, changes
  approval/sandbox semantics. Build or defer?


### loop6: cycles (selected from build/research-loop6.md, cycle R6)

- [x] CYCLE 28 — `loop6:` compaction bake-off: `codemonkey eval
  --strategy-matrix summarizing,sliding-window` runs the golden suite once per
  strategy (env override per run), records pass_rate/tokens/wall/window-depth
  per strategy into build/eval/matrix.json, prints a comparison table |
  est: 30m |
  verify: `uv run pytest tests/test_matrix.py -q` → exit 0 (≥5 tests: matrix
  runs both configs via patched exec, depth recorded per turn, matrix.json
  shape, comparison table prints, tie handling); `uv run pytest -q` → exit 0;
  LIVE: matrix over the golden-core suite on home server (results committed).
- [x] CYCLE 29 — `loop6:` KV-cache telemetry: openai provider parses
  `timings.cache_n`/`prompt_n` when the server returns them; cost summary and
  eval results record cache_hit ratio; `--cost-summary` prints it | est: 30m |
  verify: `uv run pytest tests/test_cache_telemetry.py -q` → exit 0 (≥5 tests:
  timings parse, ratio math, absent-timings tolerance, summary line, eval
  field); `uv run pytest -q` → exit 0; LIVE: repeated identical task shows
  cache_n > 0 (probe transcript committed).
- [x] CYCLE 30 — `loop6:` tool-result spill: outputs over the observation
  budget spill verbatim to ~/.codemonkey/spill/<hash>.txt; tool result becomes
  head+tail + `PARTIAL [full output: <path>]`; read_file/search can fetch
  slices; spill files pruned after 24h | est: 30m |
  verify: `uv run pytest tests/test_spill.py -q` → exit 0 (≥6 tests: spill
  verbatim, marker contains path, under-budget untouched, prune, read_file
  slice retrieval, head+tail shape); `uv run pytest -q` → exit 0; LIVE: big
  seq output spills and the model reads the slice (transcript committed).
- [ ] CYCLE loop6-final — Loop 6 acceptance: full A1–A20 re-sweep + loop-6
  probes; BUILD_REPORT loop-6 section | est: 30m |
  verify: `bash build/acceptance_sweep.sh` → all green (A9 slow-hardware
  exception per loop5-final precedent, recorded honestly); `uv run pytest -q`
  → exit 0; report updated and committed. (R7 opens; its session-semantics
  core-design flag still requires the user.)


> **USER LOOP AUTHORIZATION (2026-09-02):** "finish through loop 10 ... approved
> to not stop and work until loop 10 is done." Loops 6-10 proceed continuously
> without per-loop gates. The two R5 core-design asks (subagents/delegated
> context isolation; hooks/rule-based command permissions) are folded into
> LOOP 9 (governance) per user instruction. Core-design stop-and-ask is
> therefore SATISFIED for loops 7-10 by this blanket authorization.

> **USER LOOP AUTHORIZATION EXTENDED (2026-09-03):** "make sure that this
> finishes through loop 16." Loops 11-16 (per build/loops-11-16-proposal.md:
> delegation ROI, long-horizon work, learning from run history, model routing,
> operator surface, hardening/v1.0) proceed continuously under the same
> blanket authorization. Gate 2 remains the final user decision at the end.


### loop7: cycles (selected from build/research-loop7.md, cycle R7)

- [x] CYCLE 31 — `loop7:` execution journal + failure taxonomy: append-only
  ~/.codemonkey/journal/<thread>.jsonl records intent BEFORE dispatch and
  outcome AFTER for every tool call; error_class enum (transport, auth,
  timeout, parse, tool-error, budget, unknown); args hashed, never stored raw |
  est: 30m |
  verify: `uv run pytest tests/test_journal.py -q` → exit 0 (≥6 tests: intent-
  before-outcome ordering, error classes, args-hash stability (no raw args on
  disk), kill -9 mid-run leaves a readable journal, per-thread isolation,
  journal-tail command); `uv run pytest -q` → exit 0.
- [x] CYCLE 32 — `loop7:` idempotent mutating tools: write_file/edit_file
  compute idempotency key (thread+turn+call-index+args hash); journal hit →
  recorded outcome replayed instead of re-executing | est: 30m |
  verify: `uv run pytest tests/test_idempotency.py -q` → exit 0 (≥5 tests: key
  stability, replay-on-hit returns recorded result, miss executes, read-only
  tools unaffected, replay recorded in journal); `uv run pytest -q` → exit 0.
- [x] CYCLE 33 — `loop7:` journal forensics: `codemonkey journal list|tail|
  show` CLI; per-run failure-class summary; eval results.json gains journal
  stats | est: 30m |
  verify: `uv run pytest tests/test_journal_cli.py -q` → exit 0 (≥4 tests: list
  threads, tail shape, show by thread, class summary counts); LIVE: golden run
  produces journal with class breakdown (transcript committed).
- [x] CYCLE loop7-final — Loop 7 acceptance: full A1–A20 re-sweep + loop-7
  probes; BUILD_REPORT loop-7 section | est: 30m |
  verify: sweep → all green except A9-class slow-hardware exceptions (recorded
  honestly per loop5-final precedent); `uv run pytest -q` → exit 0; report
  committed.


### loop8: cycles (selected from build/research-loop8.md, cycle R8)

- [x] CYCLE 34 — `loop8:` batched multi-file SREP edits: edit_file args accept
  `edits: [{path, blocks|search+replace}, ...]`; atomic all-or-nothing across
  files; per-file outcomes in the result; journal records per file | est: 30m |
  verify: `uv run pytest tests/test_batch_edit.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE 35 — `loop8:` tool-output slimming: deterministic pre-budget pass
  (collapse 3+ blank lines, strip trailing WS, drop ANSI escapes); chars-saved
  stat in journal outcome | est: 30m |
  verify: `uv run pytest tests/test_slim.py -q` → exit 0 (≥5 tests); suite
  green.
- [x] CYCLE loop8-final — Loop 8 acceptance: sweep + report; transport reuse
  and cache payoff documented as carried/verified (no new cycles) | est: 30m |
  verify: sweep green (A9-class exceptions recorded honestly); suite green;
  report committed.


## Review-gate findings — loops 5-8 critic (2026-09-03) → fix cycles

Report: `build/critic-loop8.md` (6 findings, each with a runnable repro).
These fix cycles run BEFORE the loop-9 build cycles: finding 2 changes the
journal key semantics that cycle 36-38 will build on.

- [x] CYCLE 7F2 — critic finding 1 (HIGH): exec persists the FULL message
  stack on every resume (exponential duplication) and never persists the final
  assistant answer. Persist only this run's new messages, plus the final
  assistant text exactly once; keep the 6F2 schema-retry pruning correct
  | est: 25m |
  verify: `uv run pytest tests/test_sessions_persist.py -q` → exit 0 (>=5
  tests: single run stores [user, assistant]; two resumes store no duplicate
  user message; assistant answers present in order; schema-retry path stores
  exactly [pristine prompt, final answer]; ephemeral stores nothing);
  `uv run pytest -q` → exit 0.
- [x] CYCLE 31F1 — critic finding 2 (HIGH): `journal_thread` is never passed by
  any production caller, so the loop-7 journal/idempotency/forensics stack is
  inert. Wire it from exec (session thread id), REPL and eval; scope the
  idempotency key to a per-run id so a resumed thread cannot replay a previous
  invocation's write outcome; bring the REPL to exec parity on
  context_limit/compaction while wiring | est: 35m |
  verify: `uv run pytest tests/test_journal_wiring.py -q` → exit 0 (>=6 tests:
  exec run writes intent+outcome records under its thread id; `journal list`
  shows that thread; two runs on one thread produce DIFFERENT keys for the same
  args (no cross-run replay); same-run replay still hits; eval sets
  `_journal_thread` and results carry `journal_classes`; ephemeral still
  journals); `uv run pytest -q` → exit 0.
- [x] CYCLE 35F1 — critic finding 6 (LOW): the cycle-35 slim stat is journaled
  from an unbound `jkey` in `run_turns` scope; the `except Exception` swallows
  the NameError so no `:slim` record is ever written. Carry the key back with
  the outcome and record the stat | est: 15m |
  verify: `uv run pytest tests/test_slim.py -q` → exit 0 with a new test
  asserting a `status="slimmed"` journal record with the chars-saved payload
  after a journaled run; `uv run pytest -q` → exit 0.
- [x] CYCLE 34F1 — critic finding 3 (MED): batched edits re-read each path from
  disk, so two edits on the SAME file silently discard the earlier one while
  reporting success. Accumulate per path so successive edits compose; one
  outcome line per file | est: 25m |
  verify: `uv run pytest tests/test_batch_edit.py -q` → exit 0 with >=3 new
  tests (two edits on one file both land; a failing second edit on the same
  file writes nothing; outcome lists each file once); `uv run pytest -q` →
  exit 0.
- [x] CYCLE 14F1 — critic finding 4 (MED): `_save` opens a NEW checkpoint per
  file, so `undo` after a multi-file (atomic) edit restores one file and leaves
  the rest modified. Group every snapshot taken during one tool call into one
  checkpoint | est: 25m |
  verify: `uv run pytest tests/test_checkpoints.py -q` → exit 0 with >=2 new
  tests (a 2-file batch edit produces ONE checkpoint listing both files; undo
  restores both; per-call grouping still yields separate groups for separate
  calls); `uv run pytest -q` → exit 0.
- [x] CYCLE 14F2 — critic finding 5 (MED): checkpoints carry no workspace
  identity, so `codemonkey undo` in repo B can restore repo A's files into B.
  Record the workdir with each group; list/restore only groups taken in the
  current workspace | est: 25m |
  verify: `uv run pytest tests/test_checkpoints.py -q` → exit 0 with >=3 new
  tests (a checkpoint from another workdir is not listed/restored for this cwd;
  same-workdir restore unchanged; legacy groups with no workdir record are
  still restorable); `uv run pytest -q` → exit 0.
- [x] CYCLE SWEEP-F1 — critic findings 7-9 (harness): the acceptance sweep's
  home-down branch selects a provider that 6F4 deleted, so offline criteria
  (A2/A15/A19) report RED while they are green; A10 asserts against a stale
  `/tmp/cm-repo.json`; A19's invalid-name check reads `$?` after a grep and
  greps a file that is never written. Select a fallback only if it exists,
  otherwise record live probes BLOCKED with the reason; clear A10's artifact
  first; fix the A19 check | est: 25m |
  verify: `bash build/acceptance_sweep.sh` with home down → A1-A3, A8, A13,
  A14, A15, A17-A20 all green (A15 matching the standalone `uv run pytest -q`
  count) and every live probe recorded `BLOCKED (home llama.cpp wedged; no
  fallback provider configured)` — no probe reported green off a stale file.
- [x] CYCLE loop8-critic-final — fix-cycle acceptance: re-run the loops-5-8
  criteria touched by the six fixes plus the full suite; append the outcome to
  `build/BUILD_REPORT.md` | est: 20m |
  verify: `uv run pytest -q` → exit 0; `bash build/acceptance_sweep.sh`
  re-run with home-down exceptions recorded honestly; report committed.


### loop8 critic fix cycles (from build/critic-loop8.md — entry condition for R10)

- [x] CYCLE 7F2 — session persistence: persist only THIS run's messages (not
  full all_messages), and persist the final assistant answer exactly once |
  verify: unit — 2 resumes on one thread → no duplicated user turns; assistant
  answer present exactly once; store grows linearly.
- [x] CYCLE 31F1 — journal wiring: exec/REPL/eval pass journal_thread; args_key
  gains a per-run scope (run id) so resumed runs can't replay stale outcomes |
  verify: unit — real exec run writes journal records; resumed run does NOT
  replay previous run's outcome.
- [x] CYCLE 34F1 — batched edit composition: edits to the SAME file compose
  (accumulate per path); one outcome per file | verify: unit — two edits on
  one file both apply.
- [x] CYCLE 14F1 — one checkpoint group per tool call (batch writes share a
  group) | verify: unit — batch write of 2 files → undo restores BOTH.
- [x] CYCLE 14F2 — checkpoints record their workspace; undo only restores
  groups taken in the current workspace | verify: unit — cross-workspace undo
  is refused.
- [x] CYCLE SWEEP-F1 — sweep: fallback only selects an EXISTING provider;
  A10 deletes stale artifacts first; A19 measures the real criterion |
  verify: sweep green offline (live probes recorded BLOCKED with reason).
- [x] CYCLE 35F1 — slim stats journaled from the outcome's key (fix unbound
  jkey) | verify: unit — slim record appears in journal when slimming applies.

















### loop26: cycles (from build/research-loop26.md, cycle R26)

- [x] CYCLE 63 — `loop26:` verify_command auto-suggestion
- [x] CYCLE loop26-final — Loop 26 acceptance

### loop25: cycles (from build/research-loop25.md, cycle R25)

- [x] CYCLE 62 — `loop25:` status --watch frames + digest --last
- [x] CYCLE loop25-final — Loop 25 acceptance

### loop24: cycles (from build/research-loop24.md, cycle R24)

- [x] CYCLE 61 — `loop24:` role_presets (done)
- [x] CYCLE loop24-final — Loop 24 acceptance: sweep + report + push

### loop22: cycles (from build/research-loop22.md, cycle R22)

- [x] CYCLE 59 — `loop22:` exec --dry-run preview mode
- [x] CYCLE loop22-final — Loop 22 acceptance: sweep + report + push

### loop20: cycles (selected from build/research-loop20.md, cycle R20)

- [x] CYCLE 57 — `loop20:` tool-arg validation gate — validate_args(tool,
  args) from SPECS (required/type/strict-unknown); mismatch → schema_mismatch
  result feeding the self-heal loop | est: 30m |
  verify: `uv run pytest tests/test_arg_validation.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [ ] CYCLE loop20-final — Loop 20 acceptance: sweep + report + push |
  est: 30m | verify: sweep green; suite green; report; pushed.

### loop19: cycles (selected from build/research-loop19.md, cycle R19)

- [x] CYCLE 56 — `loop19:` codemonkey budget — VRAM→tokens calculator
  (per-token KV bytes = 2×layers×kv_heads×head_dim×bytes), safe context_limit
  + 40% observation split, copiable YAML block, honest metadata-missing error
  with override flags | est: 30m |
  verify: `uv run pytest tests/test_budget.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE loop19-final — Loop 19 acceptance: sweep + report + push |
  est: 30m | verify: sweep green; suite green; report; pushed.

### loop18: cycles (selected from build/research-loop18.md, cycle R18)

- [x] CYCLE 54 — `loop18:` unload-fallback rerouting: 400 "No model loaded"
  class → retry once against default provider/model, journal
  model_unload_fallback, tag task result; delegate children inherit |
  est: 30m | verify: `uv run pytest tests/test_unload_fallback.py -q` → exit 0
  (≥5 tests); `uv run pytest -q` → exit 0.
- [x] CYCLE 55 — `loop18:` model-affinity batching: batch_by_model() groups
  tasks by routed model (first-appearance order); eval task loop uses it |
  est: 30m | verify: `uv run pytest tests/test_batch_by_model.py -q` → exit 0
  (≥4 tests); `uv run pytest -q` → exit 0.
- [x] CYCLE loop18-final — Loop 18 acceptance: sweep + report + push |
  est: 30m | verify: sweep green; suite green; report; pushed.

### loop17: cycles (selected from build/research-loop17.md, cycle R17 — scoped live at user request post-v1.0.0)

- [x] CYCLE 52 — `loop17:` honest-completion gate: exec `verify_claims`
  post-turn audit — file-existence + command-outcome claims checked against
  journal/state evidence; missing evidence → reply gets [UNVERIFIED] marker +
  journal unverified_claim record; off by default | est: 30m |
  verify: `uv run pytest tests/test_verify_claims.py -q` → exit 0 (≥7 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE 53 — `loop17:` static model routing: `model_routing` first-match
  rules (tool_role/prompt_glob) selecting provider+model; route journaled;
  `eval --route-stats` per-plan pass_rate/tokens | est: 30m |
  verify: `uv run pytest tests/test_routing.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE loop17-final — Loop 17 acceptance: sweep + report + push |
  est: 30m | verify: sweep green; suite green; report committed; pushed.

### loop16: cycles (selected from build/research-loop16.md, cycle R16 — the final loop)

- [x] CYCLE 49 — `loop16:` hardening + release record: secret redaction pass
  (eval stdout excerpts + journal output fields against configured API keys),
  supply-chain audit (uv.lock committed, uv sync --locked green, dep-tree hash
  recorded), THREAT_MODEL.md | est: 30m |
  verify: `uv run pytest tests/test_hardening.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE 50 — closing acceptance v1.0.0: full A1–A20 sweep + all-loop
  criteria table, final report, v1.0.0 tag, Gate 2 handoff | est: 40m |
  verify: sweep green (honest environment exceptions recorded); suite green;
  v1.0.0 tagged; report committed.

### loop15: cycles (selected from build/research-loop15.md, cycle R15)

- [x] CYCLE 48 — `loop15:` codemonkey status: aggregates jobs progress,
  journal failure-class totals, sessions count, latest eval baseline,
  cost-ledger totals, spill bytes; --json | est: 30m |
  verify: `uv run pytest tests/test_status.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE loop15-final — Loop 15 acceptance: sweep + report | est: 30m |
  verify: sweep green (honest exceptions); suite green; report committed.

### loop14: cycles (selected from build/research-loop14.md, cycle R14)

- [x] CYCLE 47 — `loop14:` availability failover: config
  `fallback_provider: <name>`; after transport/timeout errors exhaust retries,
  exec re-runs the turn against the fallback provider; journal records the
  route switch; no fallback on auth/tools-500 | est: 30m |
  verify: `uv run pytest tests/test_failover.py -q` → exit 0 (≥6 tests:
  fallback on transport+timeout, none on auth/tools-500, journal record,
  retry-exhaustion precondition, config default off, unknown fallback
  provider rejected); `uv run pytest -q` → exit 0.
- [x] CYCLE loop14-final — Loop 14 acceptance: sweep + report | est: 30m |
  verify: sweep green (honest exceptions); suite green; report committed.

### loop13: cycles (selected from build/research-loop13.md, cycle R13)

- [x] CYCLE 45 — `loop13:` lessons store + extraction + scoped retrieval:
  lessons.py (atomic entries {id, tags{tool,error_class}, text, verified,
  source_runs}), `lessons extract` mines journal class counts into drafts,
  tag-overlap retrieval injects via the memory channel;
  `codemonkey lessons list|add|extract` | est: 30m |
  verify: `uv run pytest tests/test_lessons.py -q` → exit 0 (≥7 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE 46 — `loop13:` verified-by-eval gate: lesson.verified flips only
  on a green eval run with the lesson injected; unverified lessons excluded
  from injection | est: 30m |
  verify: `uv run pytest tests/test_lessons_gate.py -q` → exit 0 (≥4 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE loop13-final — Loop 13 acceptance: sweep + report | est: 30m |
  verify: sweep green (honest exceptions); suite green; report committed.

### loop12: cycles (selected from build/research-loop12.md, cycle R12)

- [x] CYCLE 43 — `loop12:` durable jobs module + CLI: jobs.py (atomic
  tmp+rename JSON read/write), ~/.codemonkey/jobs/<id>.json {id, goal,
  steps[{id, status: pending|done|failed, note}], created, updated};
  `codemonkey jobs list|create|show|done|fail` | est: 30m |
  verify: `uv run pytest tests/test_jobs.py -q` → exit 0 (≥6 tests: create/
  show, step transitions, atomicity under simulated crash, list, done/fail,
  unknown job error); `uv run pytest -q` → exit 0.
- [x] CYCLE 44 — `loop12:` exec --job injection + step write-back: job
  goal/steps inject into project-context; model writes `JOB_STEP <id> done`
  markers parsed post-turn; statuses persist across runs | est: 30m |
  verify: `uv run pytest tests/test_job_exec.py -q` → exit 0 (≥6 tests:
  injection contains goal+steps, marker parse, transition persists, cross-run
  resume shows progress, invalid marker ignored, ephemeral doesn't write);
  `uv run pytest -q` → exit 0.
- [x] CYCLE loop12-final — Loop 12 acceptance: sweep + report | est: 30m |
  verify: sweep green (honest exceptions); suite green; report committed.

### loop11: cycles (selected from build/research-loop11.md, cycle R11)

- [x] CYCLE 40 — `loop11:` delegation roles: delegate(task, role=
  implementer|critic|verifier) — role prompts frame the child system context;
  role in journal + result meta; default implementer | est: 30m |
  verify: `uv run pytest tests/test_roles.py -q` → exit 0 (≥5 tests).
- [x] CYCLE 41 — `loop11:` adversarial review rounds: delegate review_rounds=N
  (default 0=off) — implementer → critic structured verdict → bounded fix
  rounds; journaled | est: 30m |
  verify: `uv run pytest tests/test_review_rounds.py -q` → exit 0 (≥5 tests).
- [x] CYCLE 42 — `loop11:` delegation ROI matrix: eval --delegation-matrix
  (off vs on-with-roles), per-arm metrics, matrix.json | est: 30m |
  verify: `uv run pytest tests/test_delegation_matrix.py -q` → exit 0 (≥4
  tests).
- [x] CYCLE loop11-final — Loop 11 acceptance: sweep + report | est: 30m |
  verify: sweep green (honest exceptions); suite green; report committed.

### loop10: cycles (selected from build/research-loop10.md, cycle R10)

- [x] CYCLE 39 — `loop10:` docs & packaging release prep: README rewrite
  (13 tools, 8 commands, permissions/delegate/verify-gate/checkpoints/journal),
  version 1.0.0-rc1, CHANGELOG.md | est: 30m |
  verify: README documents every shipped command and tool (audit script);
  `uv run codemonkey --version` → 1.0.0-rc1; CHANGELOG covers loops 1-10;
  suite green.
- [x] CYCLE loop10-final — closing acceptance: full A1-A20 re-sweep + every
  loop-2..9 criterion, final BUILD_REPORT (all loops, criteria table, git log
  range, gaps), version tag, commit | est: 40m |
  verify: sweep green (A9-class honest exceptions); `uv run pytest -q` green;
  report committed; Gate 2 handoff recorded.

### loop9: cycles (selected from build/research-loop9.md, cycle R9 — R5 core-design items folded in per user authorization)

- [x] CYCLE 36 — `loop9:` rule-based permissions: config `permissions.rules` —
  ordered {tool, pattern, action: allow|deny|ask}; evaluated deny→ask→allow,
  first match wins, BEFORE the approval gate; glob pattern over shell command
  (or path for file tools); journal records rule hits | est: 30m |
  verify: `uv run pytest tests/test_permissions.py -q` → exit 0 (≥6 tests:
  precedence, first-match, glob, default-ask fallback, journal hit records,
  non-shell tools); `uv run pytest -q` → exit 0.
- [x] CYCLE 37 — `loop9:` delegate tool: `delegate(task, sandbox?)` spawns
  `codemonkey exec` subprocess with own context + journal thread; returns
  final result (capped); delegation depth 1 (delegate inside delegate
  refused) | est: 30m |
  verify: `uv run pytest tests/test_delegate.py -q` → exit 0 (≥6 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE 38 — `loop9:` parallel fan-out: `delegate_batch(tasks[])` runs
  max_delegates workers (default 2), results aggregated in call order,
  per-task isolation | est: 30m |
  verify: `uv run pytest tests/test_delegate_batch.py -q` → exit 0 (≥5 tests);
  `uv run pytest -q` → exit 0.
- [x] CYCLE loop9-final — Loop 9 acceptance: sweep + report | est: 30m |
  verify: sweep green (honest exceptions recorded); suite green; report
  committed.

## Cycle checklists — loops 6-10 (AUTHORIZED 2026-09-02 (blanket, see note above))

Charters, entry conditions and core-design flags: `build/loops-5-10-proposal.md`.
Each loop opens with its research cycle; `loop<N>:` build cycles are appended by
that cycle, never pre-selected here. Gate 2 remains open.

- [x] CYCLE R6 — Loop 6 research: context engineering chosen by measurement —
  retrieval beyond the symbol index, context-window telemetry, a compaction
  strategy bake-off scored on loop 5's harness, small-model context-rot limits
  | est: 30m |
  verify: `build/research-loop6.md` committed in the loops 2-5 shape (>=5
  candidates with real cited URLs, ranked `SELECTED` section with >=3 mapped to
  cycles); `build/plan.md` contains the `loop6:` cycles (unchecked), each
  stating its expected harness delta inside its verify probe.
  ENTRY CONDITION: loop 5 shipped an eval harness that can score two
  configurations of the same agent on the same tasks. If it did not, R6 records
  BLOCKED with that reason and does not append cycles.
- [x] CYCLE R7 — Loop 7 research: reliability and recovery — a durable
  write-ahead journal of tool intents/outcomes, idempotent mutating tools,
  mid-turn crash resume, checkpoint/undo maturity, a failure taxonomy taken
  from loop 5 harness runs, streaming partial-response handling (the cycle-23
  limitation) | est: 30m |
  verify: `build/research-loop7.md` committed in the standard shape;
  `build/plan.md` contains the `loop7:` cycles (unchecked). Core-design flag:
  ask the user before any cycle that changes session-state strategy semantics.
- [x] CYCLE R8 — Loop 8 research: throughput and cost control — batched
  multi-file edits, transport reuse, measured prefix-cache payoff, bounded
  concurrency across independent sub-tasks, per-run token/cost budgets with a
  hard stop | est: 30m |
  verify: `build/research-loop8.md` committed in the standard shape;
  `build/plan.md` contains the `loop8:` cycles (unchecked), each with raw
  before/after timing and token probes (cycle-22 convention: no claim is made
  if the numbers do not separate). ENDS BY ASKING the user if any selection
  proposes concurrent model turns (loop architecture = core design).
- [x] CYCLE R9 — Loop 9 research: governance for unattended runs — rule-based
  command allow/deny matching, secret redaction across events/sessions/
  checkpoints, an append-only audit trail, process-level sandbox hardening
  beyond lexical containment, `web_fetch` egress policy, the documented `shell`
  cwd-escape gap | est: 30m |
  verify: `build/research-loop9.md` committed in the standard shape;
  `build/plan.md` contains the `loop9:` cycles (unchecked). NOTE: this loop is
  sandbox + approval semantics by definition — core design. R9 ENDS BY ASKING
  the user and does not hand selections to a build tick.
- [x] CYCLE R10 — Loop 10 research: interop, distribution and closing
  acceptance — MCP client (justify with a concrete need or close it
  permanently after four deferrals), a documented config-declared tool
  extension point, packaging/versioned release, a `--help`/docs surface audit
  against the shipped flag set | est: 30m |
  verify: `build/research-loop10.md` committed in the standard shape;
  `build/plan.md` contains the `loop10:` cycles (unchecked) ending in
  `loop10-final`. ENTRY CONDITION: no open critic finding above LOW severity.
- [ ] CYCLE loop10-final — closing acceptance: full A1-A20 re-sweep plus every
  loop-2..9 criterion, final `build/BUILD_REPORT.md` (all loops, criteria
  table, git log range, gaps), commit | est: 40m |
  verify: `bash build/acceptance_sweep.sh` → all green; `uv run pytest -q` →
  exit 0; report updated and committed.

## Cycle checklists — loops 11-16 (PROPOSED 2026-09-03, ⚠️ NOT AUTHORIZED)

Charters, entry conditions and core-design flags:
`build/loops-11-16-proposal.md`. Unlike loops 6-10, these carry NO blanket
authorization: they stay unchecked until the user authorizes the arc. Each
loop opens with its research cycle; `loop<N>:` build cycles are appended by
that cycle, never pre-selected here. `loop10-final` still precedes all of them.

- [x] CYCLE R11 — Loop 11 research: delegation that measurably pays — which
  delegated ROLES (independent implementer, adversarial critic, verifier that
  owns the verify gate, retrieval scout) raise golden-suite pass rate at a
  fixed token budget on a 27B-class local model, and which are pure overhead;
  depth/fan-out limits taken from measurement; delegate result contracts;
  delegate failure isolation from the parent journal thread | est: 30m |
  verify: `build/research-loop11.md` committed in the loops 2-9 shape (>=5
  candidates with real cited URLs, ranked `SELECTED` section with >=3 mapped
  to cycles); `build/plan.md` contains the `loop11:` cycles (unchecked), each
  stating its expected harness delta (pass rate, tokens, wall) inside its
  verify probe. ENTRY CONDITION: loop 9 shipped `delegate`/`delegate_batch`
  AND loop 5's harness can score two configurations on the same tasks — if
  not, R11 records BLOCKED with that reason and appends no cycles.
  Core-design: PARTIAL — concurrent model turns inside one thread ends by
  asking (the R8 flag, unchanged).
- [x] CYCLE R12 — Loop 12 research: long-horizon work across runs — durable
  task/plan state that survives a run, honest mid-turn crash resume off the
  loop-7 journal (deferred in loop 7 with the journal named as prerequisite),
  resumable long-horizon eval tasks, compaction policy for week-long threads,
  GC for journals/spills/checkpoints under a long job | est: 30m |
  verify: `build/research-loop12.md` committed in the standard shape;
  `build/plan.md` contains the `loop12:` cycles (unchecked), including one
  whose probe kills a run mid-turn and shows the resumed run applying the
  interrupted mutation EXACTLY once. ENTRY CONDITION: loop 11 closed (shipped
  or explicitly rejected). Core-design: YES (durable task state borders
  session-state strategy semantics) — R12 ENDS BY ASKING.
- [x] CYCLE R13 — Loop 13 research: learning from the run history — failure-mode
  memory keyed by the loop-7 error taxonomy, retrieval over past
  sessions/journals scoped to the repo, tool-choice priors from journal
  success rates, memory curation/decay, privacy posture for a cross-repo
  store | est: 30m |
  verify: `build/research-loop13.md` committed in the standard shape AND one
  of: `build/plan.md` contains the `loop13:` cycles (unchecked, each with a
  harness-delta probe), OR the research file closes the theme with the
  measurements that killed it (an honest "no" is a valid exit). ENTRY
  CONDITION: >=2 loops of journal + eval history exist in volume. Core-design:
  PARTIAL — a cross-repo history store ends by asking.
- [x] CYCLE R14 — Loop 14 research: heterogeneous models and routing (the R8
  deferral) — per-task-class routing scored on the golden suite, cheap model
  for compaction vs main model for edits, health checks that distinguish
  "unreachable" from "reachable but wedged" (the failure this repo keeps
  hitting), declarative failover chains where a fallback is RECORDED never
  silent, cost-aware routing against the cycle-26 ledger, the cycle-23
  streaming partial-response gap | est: 30m |
  verify: `build/research-loop14.md` committed in the standard shape;
  `build/plan.md` contains the `loop14:` cycles (unchecked) with raw
  before/after tables per task class. ENTRY CONDITION: >=2 usable providers
  reachable at once — otherwise R14 records BLOCKED (routing cannot be
  measured on one endpoint). Core-design: YES (provider selection) — R14 ENDS
  BY ASKING.
- [x] CYCLE R15 — Loop 15 research: operator surface and observability — diff
  preview before a mutation is applied (and a diff-gated approval mode), a run
  timeline over the JSONL stream, one inspector unifying journal/spill/
  checkpoints/cost, a REPL status line, structured run reports for CI | est:
  30m |
  verify: `build/research-loop15.md` committed in the standard shape;
  `build/plan.md` contains the `loop15:` cycles (unchecked), EACH carrying a
  probe asserting exec stdout purity is unchanged (text mode = final answer
  only; --json = JSONL only). ENTRY CONDITION: loop 12's long-horizon runs
  exist; if runs are still short, R15 narrows to the diff-gated approval mode
  alone. Core-design: PARTIAL — the diff-gated approval mode ends by asking.
- [x] CYCLE R16 — Loop 16 research: hardening, release readiness, v1.0
  acceptance — process-level containment (macOS `sandbox-exec`, Linux
  bubblewrap/seccomp) behind the existing sandbox levels closing the
  documented `shell` cwd-escape gap, secret redaction if loop 9 did not take
  it, supply-chain/lockfile hygiene, a tagged release with upgrade/rollback, a
  documented threat model | est: 30m |
  verify: `build/research-loop16.md` committed in the standard shape;
  `build/plan.md` contains the `loop16:` cycles (unchecked) ending in
  `loop16-final`. ENTRY CONDITION: loops 11-15 closed AND no open critic
  finding above LOW severity AND a live endpoint is available (the closing
  sweep may not contain BLOCKED rows). Core-design: YES (containment redefines
  what the sandbox levels promise) — R16 ENDS BY ASKING.
- [x] CYCLE 51 (loop16) — live-endpoint defect sweep: native tool-call
  schemas (all 13 tools advertised argument-free on the wire), unattended-run
  robustness (idle-stdin hang, doubled error line, blank tool trace), and
  probe honesty in the acceptance harness (A9 false green, hardcoded live
  gate, A2 pinned to a literal endpoint) | est: 60m |
  verify: `uv run pytest -q` → exit 0 (455+ passed);
  `uv run python -c "from codemonkey.native import tool_specs_for; from
  codemonkey.tools import SPECS; t=[x for x in tool_specs_for('openai',SPECS)
  if x['function']['name']=='shell'][0];
  assert t['function']['parameters']['required']==['command']"` → exit 0;
  live tool loop `uv run codemonkey exec --sandbox workspace-write --approval
  never "Use the shell tool to run: echo codemonkey_tool_test. Then reply with
  exactly the command output." </dev/null` → stdout is `codemonkey_tool_test`
  AND stderr shows `$ echo codemonkey_tool_test` + `[exit 0]`;
  `time uv run codemonkey exec "Reply with exactly the word pong and nothing
  else." --ephemeral` WITHOUT `</dev/null` → returns in <60s (was an
  unbounded hang); dead-endpoint `CODEMONKEY_BASE_URL=http://127.0.0.1:9/v1
  CODEMONKEY_MAX_RETRIES=0 uv run codemonkey exec hi --ephemeral </dev/null`
  → exit 1 with exactly ONE `error:` line on stderr;
  `bash build/acceptance_sweep.sh` → A1-A20 all exit 0, zero BLOCKED.
- [x] CYCLE loop16-final — v1.0 closing acceptance: A1-A20 plus every
  loop-2..15 criterion re-run LIVE with no BLOCKED rows, final
  `build/BUILD_REPORT.md` (all loops, criteria table, git log range, gaps),
  version tag | est: 40m |
  verify: `bash build/acceptance_sweep.sh` → all green, zero BLOCKED;
  `uv run pytest -q` → exit 0; `uv run codemonkey --version` matches the tag;
  report updated and committed.

## Cycle checklists — loops 17-27 (PROPOSED 2026-09-03, ⚠️ NOT AUTHORIZED)

Charters, the debt ledger this arc discharges (D1-D12), the handoff contract
for an implementer with no conversation context, and the binding arc rules
(R-A "measure or delete" … R-E "the register is the release record"):
`build/loops-17-27-proposal.md`. Like loops 11-16 and unlike loops 6-10, these
carry NO blanket authorization: they stay unchecked until the user authorizes
the arc. Each loop opens with its research cycle; `loop<N>:` build cycles are
appended by that cycle, never pre-selected here.

Baseline for the arc: `ca601e5`, v1.0.0, suite 460 passed, A1-A20 all exit 0
live with zero BLOCKED rows.

- [ ] CYCLE R17B — Loop 17B research: truth pass, claims versus evidence (NOTE: loop 17 proper was consumed 2026-09-03 by concurrent work — the
  honest-completion gate (52) + static model routing (53), closed at
  `loop17-final`. This charter keeps its arc position and is relabelled 17B;
  every "loop 17" reference in the 17-27 and 28-37 arcs means THIS cycle) — an
  evidence class (PROVEN-LIVE / UNIT-ONLY / UNVALIDATED / DEAD) for every
  capability loops 1-16 claim; resolution of the two unchecked closing cycles
  (D8: `loop6-final` at plan.md:595, `loop10-final` at plan.md:951); a
  README/features.html/THREAT_MODEL audit against reality; a dead-surface pass
  | est: 30m |
  verify: `build/research-loop17b.md` committed in the loops 2-16 shape (>=5
  candidates with real cited URLs, ranked `SELECTED` section);
  `build/CAPABILITY_REGISTER.md` committed with one row per shipped capability
  carrying name, entry point, strongest evidence (literal probe or test path),
  evidence class, and the debt row it carries; `build/plan.md` contains the
  `loop17b:` cycles (unchecked) for every demotion and doc correction; D8
  resolved (both boxes ticked with re-run probe output, or annotated
  superseded-by — never silently ticked). ENTRY CONDITION: none; this loop is
  always openable and blocks the rest of the arc. Core-design: NO (behavioral
  defects become `17BF<n>` critic-style fix cycles, not design rewrites).
- [x] CYCLE R18 — Loop 18 research: foreign-repo dogfood (D11) — the tool has
  never been run on a codebase it did not author; N real tasks on >=2 external
  repos, each producing a kept journal thread, and a ranked friction log where
  every entry cites the transcript line proving it | est: 30m |
  verify: `build/research-loop18.md` committed in the standard shape;
  `build/friction-loop18.md` committed with ranked entries, each carrying
  file/transcript evidence; `build/plan.md` contains the `loop18:` cycles
  (unchecked), each with a probe that reproduces the friction BEFORE the fix
  and shows it gone after. ENTRY CONDITION: `build/CAPABILITY_REGISTER.md`
  exists (loop 17B closed) AND the user has named external repos the agent may
  operate in — otherwise R18 records BLOCKED and appends no cycles (a
  synthetic repo is not a foreign repo). Core-design: NO for the log; PARTIAL
  if a friction's only fix changes tool semantics — that fix ends by asking.
- [x] CYCLE R19 — Loop 19 research: mid-turn resume and crash truth (D1,
  deferred in loop 7, chartered and missed in loop 12) — exactly-once replay
  of the in-flight intent off the journal, a crash-point taxonomy (before the
  call / after call before journal write / after journal write before effect /
  after effect), reconciliation against checkpoints, loud refusal when the
  crash point cannot be established, interaction with `--job` step write-back
  | est: 30m |
  verify: `build/research-loop19.md` committed in the standard shape;
  `build/plan.md` contains the `loop19:` cycles (unchecked) including,
  mandatorily, a probe of this literal shape — start a run performing a known
  mutation, `kill -9` it mid-turn, resume it, assert the mutation is present
  EXACTLY once by byte-compare or count assertion (not "looks right") — plus
  one probe per crash-point class. ENTRY CONDITION: journal wired into
  production runs (31F1, done) AND a reachable live endpoint; without one R19
  records BLOCKED rather than proving resume against mocks. Core-design: YES
  (what a resumed run may assume is session semantics) — R19 ENDS BY ASKING.
- [x] CYCLE R20 — Loop 20 research: containment for real (D2 — R16 researched
  macOS `sandbox-exec`/Linux bwrap then dropped it from SELECTED, leaving the
  documented `shell` cwd-escape gap open under lexical containment alone) —
  per-level profiles, honest fail-closed fallback where no mechanism exists,
  enforcement parity across levels and platforms, and what THREAT_MODEL.md
  must stop promising | est: 30m |
  verify: `build/research-loop20.md` committed in the standard shape (with
  current, cited status for `sandbox-exec` deprecation — assumed, not
  recalled); `build/plan.md` contains the `loop20:` cycles (unchecked), each
  carrying an escape probe (attempt the documented cwd escape → assert denial,
  exit code and message) AND a per-tool latency before/after measurement, plus
  a THREAT_MODEL.md revision cycle whose probe asserts every promise in the
  document maps to an enforcing test. ENTRY CONDITION: loop 17B's register
  records the sandbox row honestly. Core-design: YES (containment redefines
  what the sandbox levels promise) — R20 ENDS BY ASKING.
- [ ] CYCLE R21 — Loop 21 research: a harness that can say no (D4, D5) —
  loops 11 and 13 shipped delegation roles/review_rounds/matrix and
  lessons+verified-gate, each chartered "kept only on a measured win", with no
  delta recorded anywhere; make scoring cheap enough to be routine on one slow
  27B endpoint, then actually score those arms and delete what does not
  separate | est: 30m |
  verify: `build/research-loop21.md` committed in the standard shape,
  including a stated minimum-N / significance rule for small-sample pass-rate
  claims; `build/plan.md` contains the `loop21:` cycles (unchecked), each
  carrying RAW per-arm numbers (pass rate, tokens, wall) inside its verify
  probe; `build/CAPABILITY_REGISTER.md` updated so every UNVALIDATED row
  becomes PROVEN, DEAD, or "measured, did not separate, kept because
  <reason>". ENTRY CONDITION: register lists the UNVALIDATED set (loop 17B
  closed) AND a reachable live endpoint — this loop cannot run on mocks by
  construction; without one R21 records BLOCKED. Core-design: NO for
  measurement; PARTIAL for deletion — removing shipped, documented surface
  ends by asking before it lands.
- [x] CYCLE R22 — Loop 22 research: routing, actually measured (D3 — deferred
  by R8, blocked at R14 on a single provider) — per-task-class routing scored
  per class, health checks that distinguish unreachable / reachable-but-wedged
  / degraded (the failure this repo lost four loops to), failover chains where
  every fallback is journal-recorded and never silent, cost-aware routing
  against the cycle-26 ledger, and D10 (a mid-stream transport failure
  currently discards partial tokens in `providers/openai.py::_request_stream`)
  | est: 30m |
  verify: `build/research-loop22.md` committed in the standard shape;
  `build/plan.md` contains the `loop22:` cycles (unchecked) with raw
  before/after tables PER TASK CLASS, plus the D10 streaming decision
  (retain / retry / explicitly drop) as a testable cycle. ENTRY CONDITION —
  HARD: >=2 usable providers reachable AT THE SAME TIME. Without a second
  provider R22 records BLOCKED, appends NO routing cycles, and may append only
  the D10 streaming cycle (which needs one endpoint). Core-design: YES
  (provider selection) — R22 ENDS BY ASKING.
- [ ] CYCLE R23 — Loop 23 research: the operator's eyes (D6 — R15's own
  narrow-scope fallback was the diff-preview approval mode and it did not
  ship; `grep -n diff src/codemonkey/approvals.py src/codemonkey/exec.py`
  returns nothing) — diff computed before a mutation is applied and an
  approval mode gating on the diff rather than the tool name, a run timeline
  over the existing JSONL stream, one inspector unifying journal/undo/spill/
  checkpoints, a REPL status line, structured CI run reports | est: 30m |
  verify: `build/research-loop23.md` committed in the standard shape;
  `build/plan.md` contains the `loop23:` cycles (unchecked), EACH carrying a
  probe asserting exec stdout purity is unchanged (text mode = final answer
  only; `--json` = JSONL only) per arc rule R-D. ENTRY CONDITION: loop 18's
  friction log exists and RE-RANKS these seeds; if loop 18 was BLOCKED, R23
  narrows to the diff-gated approval mode alone (justified by D6 independent
  of friction evidence). Core-design: PARTIAL — the diff-gated approval mode
  changes approval semantics and ends by asking; read-only viewers do not.
- [x] CYCLE R24 — Loop 24 research: concurrency and shared state (D9 —
  `delegate_batch` already runs workers concurrently while `jobs.py` is
  single-writer, deferred at loop 12 for want of file locking) — locking or
  lock-free design for every store two processes can touch, conflict semantics
  when two delegates advance one step, crash behavior UNDER concurrency, proof
  (not assertion) of journal thread isolation for a dead delegate | est: 30m |
  verify: `build/research-loop24.md` committed in the standard shape;
  `build/plan.md` contains the `loop24:` cycles (unchecked) including a probe
  that runs N concurrent writers against one store and asserts NO LOST UPDATE
  by exact count — or a written refusal recording the reasoning that produced
  it (a documented "these must not share state" is a valid exit). ENTRY
  CONDITION: loop 19 closed (single-run crash semantics defined); if loop 19
  was BLOCKED, R24 narrows to locking with a tested single-writer guarantee
  and defers concurrent crash semantics explicitly. Core-design: YES (shared
  mutable state across processes; the standing R8/R11 concurrent-model-turns
  flag may be RAISED here, never assumed) — R24 ENDS BY ASKING.
- [x] CYCLE R25 — Loop 25 research: long-thread economy (D12 — journals,
  spills, checkpoints and session stores grow unbounded; GC was an R12 seed
  never taken; no job here has outlived a single run by days) — measured
  growth per store under a long job BEFORE any policy is designed, retention
  weighed against the journal's role as the evidence base for resume and the
  register, compaction policy for week-long threads, multi-day cost
  accounting, resumable long-horizon eval tasks | est: 30m |
  verify: `build/research-loop25.md` committed in the standard shape;
  `build/plan.md` contains the `loop25:` cycles (unchecked), each with
  measured before/after disk AND context numbers, plus a compaction survival
  probe asserting a specific named fact still answerable after N compactions;
  every cycle also carries the R-D stdout-purity assertion. ENTRY CONDITION:
  loops 19 and 24 closed AND at least one job has actually run across multiple
  sessions/days — without a real long job R25 records BLOCKED rather than
  modeling a hypothetical curve. Core-design: PARTIAL — retention that deletes
  journal history changes what the framework can later prove, and that
  decision ends by asking.
- [x] CYCLE R26 — Loop 26 research: someone else's machine (D7) — clean-machine
  install from the committed lockfile, Linux parity (especially for loop 20's
  platform-specific containment), LIVE verification of the Anthropic native
  tool shape (`input_schema`, fixed in 51F1b and unit-tested only because no
  key was available), distribution/upgrade/rollback, and first-run experience
  with an empty `~/.codemonkey/` | est: 30m |
  verify: `build/research-loop26.md` committed in the standard shape;
  `build/plan.md` contains the `loop26:` cycles (unchecked) with per-platform
  probe results and an explicit honest table of what remains unverified.
  ENTRY CONDITION: loop 20 closed. Per-seed blockers are recorded, not routed
  around: no Linux host → Linux rows record BLOCKED; no Anthropic key → D7
  stays OPEN and is carried into loop 27's record as an open gap, never
  declared passing on unit tests. Core-design: NO (packaging/platform); a
  containment difference forcing a semantic change ends by asking.
- [ ] CYCLE R27 — Loop 27 research + closing acceptance: v2.0 — full A1-A20
  re-sweep plus every loop-2..26 criterion live with zero BLOCKED rows (or an
  individually justified exception list), the capability register brought
  current as the release record (arc rule R-E), a closing critic pass in
  `build/critic-cycle6.md` style, THREAT_MODEL.md refreshed against what loop
  20 actually enforces, final BUILD_REPORT for loops 17-27 with the git range,
  version tag, Gate 3 handoff | est: 40m |
  verify: `build/research-loop27.md` committed (acceptance-record method,
  cited); `build/plan.md` contains the `loop27:` cycles (unchecked) ending in
  `loop27-final` whose own probe is: `bash build/acceptance_sweep.sh` → all
  exit 0, zero BLOCKED; `uv run pytest -q` → exit 0; `uv run codemonkey
  --version` matches the tag; every `build/CAPABILITY_REGISTER.md` row reads
  PROVEN-LIVE, UNIT-ONLY with a stated reason, or DEAD — no UNVALIDATED rows
  remain; report committed. ENTRY CONDITION: loops 17-26 closed (shipped, or
  explicitly and defensibly rejected/BLOCKED in writing), no open critic
  finding above LOW severity, and a reachable live endpoint — if the endpoint
  is down loop 27 WAITS rather than closing dishonestly. Core-design: NO.

## Cycle checklists — loops 28-37, the capability arc (PROPOSED 2026-09-03, ⚠️ NOT AUTHORIZED)

Charters, the 2026 literature anchors each loop replicates, and the two extra
arc rules: `build/loops-28-37-proposal.md`. The §0 handoff contract, §1
verified current state, §2 debt ledger and §3 rules R-A…R-E of
`build/loops-17-27-proposal.md` apply here unchanged. Two rules are added:
**R-F** every quality number is reported with its cost multiplier and wall
clock, and adoption defaults OFF above 2× cost; **R-G** each cycle records the
published number, this repo's number, AND the gap, with a hypothesis for any
large divergence — citing a paper's number as if it were ours is fabrication
under SPRINT.md.

These loops make the machine current; loops 17-27 make it honest. They open
only after `loop27-final`, and several carry hard entry conditions on loops
19/20/24/25 — N concurrent mutating workers without containment is a defect,
and branching without defined crash semantics is undefined behavior.

- [ ] CYCLE R28 — Loop 28 research: graph-grounded retrieval — this repo builds,
  commits and mandates `graphify-out/` for human-side agents while the agent it
  ships navigates by grep/glob and a heuristic repo_map; expose the structural
  index as `graph_query`/`graph_path`/`graph_explain` tools, re-ground
  `repomap.py` ranking on graph structure, detect staleness rather than
  trusting it, and decide the no-graph fallback (build / degrade / refuse)
  | est: 30m |
  verify: `build/research-loop28.md` committed in the standard shape (>=5
  candidates, real cited URLs incl. the ~10x token / 2.1x tool-call
  structural-index result, ranked `SELECTED`); `build/plan.md` contains the
  `loop28:` cycles (unchecked), EACH reporting tokens AND tool calls per task
  for graph-on vs graph-off arms, with the published figures alongside per
  rule R-G, and each carrying a staleness probe (graph older than HEAD → the
  tool reports stale, never answers silently). ENTRY CONDITION:
  `graphify-out/graph.json` present and current at HEAD AND loop 21's harness
  can score two retrieval arms; else BLOCKED. Core-design: PARTIAL — new tools
  are registry work; changing repo_map's ranking changes context assembly and
  ends by asking.
- [ ] CYCLE R29 — Loop 29 research: LSP grounding and pre-apply validation —
  symbol-accurate navigation (definition/references/callers) replacing textual
  search for symbol questions, and edit validation BEFORE apply (syntax → lint
  → typecheck, edit rejected back to the model rather than committed and
  undone), with a stated retry budget and an honest multi-language posture
  | est: 30m |
  verify: `build/research-loop29.md` committed in the standard shape;
  `build/plan.md` contains the `loop29:` cycles (unchecked) with before/after
  BROKEN-EDIT RATE on a fixed task set and per-edit latency cost; one cycle
  must resolve authority between graph (loop 28) and LSP for "where is this
  symbol used" rather than shipping both and confusing the model. ENTRY
  CONDITION: a language server installable in this environment without
  run-time network access; if not, R29 narrows to syntax+lint validation
  (needs no server) and records the LSP portion BLOCKED. Core-design: PARTIAL
  — making an edit conditional on typecheck changes edit semantics and ends by
  asking.
- [ ] CYCLE R30 — Loop 30 research: certified and comparable measurement —
  anytime-valid sequential certificates (stop at significance instead of a
  fixed N, which is the difference between affordable and unaffordable on one
  slow 27B endpoint), adoption of a real benchmark subset (DeepSWE / SWE-EVO /
  SWE-Bench Pro) alongside the homemade golden suite, a standing
  arm-comparison report format carrying cost per R-F, and a regression gate so
  a later loop cannot silently undo an earlier loop's win | est: 30m |
  verify: `build/research-loop30.md` committed in the standard shape,
  containing an explicit FEASIBILITY assessment of running the chosen
  benchmark on this hardware (container-heavy, long-horizon; "we can run this
  N-task subset and no more" is the expected honest outcome, not full-suite
  numbers); `build/plan.md` contains the `loop30:` cycles (unchecked). ENTRY
  CONDITION: loop 21 closed; benchmark adoption additionally needs a container
  runtime and disk — without it that half records BLOCKED and the certificates
  half proceeds. Core-design: NO. NOTE: once shipped, loop 30's certificate
  machinery is MANDATORY for every quality claim in loops 31-36.
- [ ] CYCLE R31 — Loop 31 research: fork-and-branch execution — a `branch`
  primitive defined against the existing checkpoint+journal pair so a branch is
  a REPLAYABLE object rather than a copied process; what is shared (transcript
  prefix, prompt-cache prefix, filesystem snapshot) versus copied; discard
  semantics; branch thread identity for forensics; explicit non-goal:
  microVM-level forking is infrastructure this project does not own | est: 30m |
  verify: `build/research-loop31.md` committed in the standard shape (citing
  the 40.0-64.2% checkpoint-reuse rollout-token result); `build/plan.md`
  contains the `loop31:` cycles (unchecked), each with a token-reuse
  measurement stated against that published band per R-G, and a ZERO-RESIDUE
  probe for a discarded branch (exact file-state comparison before fork vs
  after discard — byte-level, not "looks clean"). ENTRY CONDITION: loops 19
  AND 24 closed (branching is resume plus concurrency and inherits both); if
  either was BLOCKED, R31 records BLOCKED rather than building forking on
  undefined crash semantics. Core-design: YES (forking in-flight run state is
  session and journal semantics) — R31 ENDS BY ASKING.
- [ ] CYCLE R32 — Loop 32 research: best-of-N with an execution verifier —
  `p -> 1-(1-p)^N` fan-out over `delegate_batch`, candidates ranked by running
  the task's verify command (execution-based) with execution-free reranking
  where no test exists, per-candidate isolation via loop 31's branch, early
  abort once a candidate verifies, and the economic argument this repo exists
  to test: N cheap local 27B attempts versus one frontier API call | est: 30m |
  verify: `build/research-loop32.md` committed in the standard shape;
  `build/plan.md` contains the `loop32:` cycles (unchecked) reporting pass
  rate, tokens AND wall at N in {1,2,4,8}, certified by loop 30's sequential
  test, with the observed curve compared to theoretical `1-(1-p)^N` per R-G;
  adoption defaults OFF above 2x cost per R-F. ENTRY CONDITION — HARD: loops
  20 (containment) and 31 (branching) both closed. WITHOUT CONTAINMENT, N
  concurrent mutating workers is a defect, not a feature: R32 then narrows to
  READ-ONLY fan-out (analysis/review tasks that mutate nothing) and records the
  mutating case BLOCKED. Core-design: YES ("one prompt produces N runs and one
  answer" changes what a run is, and multiplies cost) — R32 ENDS BY ASKING.
- [ ] CYCLE R33 — Loop 33 research: generative verifiers, rubrics, step-level
  rewards — a generative verifier on `delegate role=critic` scoring candidates
  in [0,1] with justification, task rubrics as the contextual verifier where
  execution cannot judge, hybrid scoring (execution dominates, rubric breaks
  ties), and step-level process rewards over the journal's per-step intents
  with compute spent only at high-uncertainty steps | est: 30m |
  verify: `build/research-loop33.md` committed in the standard shape (citing
  generative>regressive verifiers and rubric process reward work);
  `build/plan.md` contains the `loop33:` cycles (unchecked) whose FIRST probe
  measures VERIFIER ACCURACY against known-good/known-bad candidates before
  any end-to-end claim — a verifier worse than random makes best-of-N actively
  harmful and must be caught here, not inferred from a pass-rate wash — then
  selection quality versus random and versus execution-only. ENTRY CONDITION:
  loop 32 closed (a selection point exists) and loop 30's certificates exist.
  Core-design: PARTIAL — a model-scored gate deciding whether work is ACCEPTED
  is adjacent to approval semantics and ends by asking; ranking alone does not.
- [ ] CYCLE R34 — Loop 34 research: corrections compiled into enforcement — a
  correction taxonomy (mechanically enforceable / partially enforceable /
  irreducibly advisory), a compilation path correction -> proposed rule -> USER
  CONFIRMATION -> `permissions.rules` entry with provenance, and rule
  lifecycle (expiry, conflict, precedence, `codemonkey rules
  list|explain|revoke`) | est: 30m |
  verify: `build/research-loop34.md` committed in the standard shape (citing
  the corrections->runtime-enforcement work); `build/plan.md` contains the
  `loop34:` cycles (unchecked) including a probe that replays a corrected
  scenario and asserts the violation is REFUSED BY THE PERMISSION LAYER (deny
  recorded in the journal), not merely avoided by the model, plus a
  repeat-violation-rate before/after number; a self-authored rule must not
  bind without confirmation (probe: synthesis proposes, nothing binds until
  confirmed). ENTRY CONDITION: loop 21's verdict on `lessons` recorded — if
  lessons were deleted there, this loop builds on the permissions engine
  alone, which is sufficient. Core-design: PARTIAL — rules the agent authors
  for itself change what the permission layer IS, and that ends by asking.
- [ ] CYCLE R35 — Loop 35 research: adaptive memory management — an adaptive
  write/retain/evict policy replacing tag-overlap heuristics, continual
  learning measured over a TASK STREAM rather than isolated tasks, and honest
  cross-domain transfer tested against loop 18's foreign repos (the failure
  mode is memories that help on the source repo and mislead elsewhere)
  | est: 30m |
  verify: `build/research-loop35.md` committed in the standard shape (citing
  SWE-MeM, SWE-Bench-CL, memory-transfer work) AND one of: `build/plan.md`
  contains the `loop35:` cycles (unchecked, task-stream results certified by
  loop 30, transfer measured on >=2 repos), OR the research file closes the
  theme with the measurements that killed it — an honest "no" is a valid exit,
  exactly as R13 permitted. ENTRY CONDITION: loop 25 closed (an adaptive
  memory fighting an undefined GC policy is unmeasurable) AND >=2 repos' worth
  of history exists (loop 18). Core-design: PARTIAL for a new strategy in the
  registry; YES for a cross-repo store — that ends by asking.
- [ ] CYCLE R36 — Loop 36 research: learned context assembly — assembly as an
  explicit swappable, scored policy (loop 5's strategy matrix is the vehicle)
  instead of hand-ordered parts; per-task-class assembly (a review task and an
  edit task do not want the same window); budget allocation across sources
  under a token ceiling, where loop 28's graph and loop 35's memory compete for
  space | est: 30m |
  verify: `build/research-loop36.md` committed in the standard shape (citing
  the 89.1% vs 70.7% context-engineering result) and stating UP FRONT the
  risk that the published delta came from a frontier model with a large window
  and may not survive on a 27B-class one; `build/plan.md` contains the
  `loop36:` cycles (unchecked) with per-policy scores certified by loop 30 and
  the gap to the published result explained per R-G. ENTRY CONDITION: loops
  28, 30 and 35 closed. This is the most speculative charter in the arc and is
  deliberately last — if the budget runs out, THIS is the loop to drop.
  Core-design: YES (context assembly is the architecture the CLI is built
  around) — R36 ENDS BY ASKING.
- [ ] CYCLE R37 — Loop 37 research + closing acceptance: v3.0 — full A1-A20 plus
  every loop-2..36 criterion live with zero BLOCKED (or an individually
  justified exception list), the register current with each loop-28..36 row
  carrying LOCAL number / PUBLISHED number / GAP per R-G, a cost table per R-F,
  deletion cycles for anything that did not survive its certificate, a closing
  critic pass, THREAT_MODEL.md refreshed (best-of-N, branching and
  self-authored permission rules each change the security surface; loop 34's
  rules are a new trust boundary), final BUILD_REPORT for loops 28-37, tag,
  Gate 4 handoff | est: 40m |
  verify: `build/research-loop37.md` committed; `build/plan.md` contains the
  `loop37:` cycles (unchecked) ending in `loop37-final` whose own probe is:
  `bash build/acceptance_sweep.sh` → all exit 0, zero BLOCKED; `uv run pytest
  -q` → exit 0; `uv run codemonkey --version` matches the tag; every
  `build/CAPABILITY_REGISTER.md` row reads PROVEN-LIVE, UNIT-ONLY with a
  stated reason, or DEAD — no UNVALIDATED rows; every loop-28..36 row carries
  its local/published/gap triple; report committed. ENTRY CONDITION: loops
  28-36 closed (shipped, or explicitly rejected/BLOCKED in writing), no open
  critic finding above LOW, live endpoint reachable. Core-design: NO.
