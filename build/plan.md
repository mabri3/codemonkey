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

- [ ] CYCLE 7F2 — session persistence: persist only THIS run's messages (not
  full all_messages), and persist the final assistant answer exactly once |
  verify: unit — 2 resumes on one thread → no duplicated user turns; assistant
  answer present exactly once; store grows linearly.
- [ ] CYCLE 31F1 — journal wiring: exec/REPL/eval pass journal_thread; args_key
  gains a per-run scope (run id) so resumed runs can't replay stale outcomes |
  verify: unit — real exec run writes journal records; resumed run does NOT
  replay previous run's outcome.
- [ ] CYCLE 34F1 — batched edit composition: edits to the SAME file compose
  (accumulate per path); one outcome per file | verify: unit — two edits on
  one file both apply.
- [ ] CYCLE 14F1 — one checkpoint group per tool call (batch writes share a
  group) | verify: unit — batch write of 2 files → undo restores BOTH.
- [ ] CYCLE 14F2 — checkpoints record their workspace; undo only restores
  groups taken in the current workspace | verify: unit — cross-workspace undo
  is refused.
- [ ] CYCLE SWEEP-F1 — sweep: fallback only selects an EXISTING provider;
  A10 deletes stale artifacts first; A19 measures the real criterion |
  verify: sweep green offline (live probes recorded BLOCKED with reason).
- [ ] CYCLE 35F1 — slim stats journaled from the outcome's key (fix unbound
  jkey) | verify: unit — slim record appears in journal when slimming applies.

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
- [ ] CYCLE R10 — Loop 10 research: interop, distribution and closing
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

- [ ] CYCLE R11 — Loop 11 research: delegation that measurably pays — which
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
- [ ] CYCLE R12 — Loop 12 research: long-horizon work across runs — durable
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
- [ ] CYCLE R13 — Loop 13 research: learning from the run history — failure-mode
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
- [ ] CYCLE R14 — Loop 14 research: heterogeneous models and routing (the R8
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
- [ ] CYCLE R15 — Loop 15 research: operator surface and observability — diff
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
- [ ] CYCLE R16 — Loop 16 research: hardening, release readiness, v1.0
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
- [ ] CYCLE loop16-final — v1.0 closing acceptance: A1-A20 plus every
  loop-2..15 criterion re-run LIVE with no BLOCKED rows, final
  `build/BUILD_REPORT.md` (all loops, criteria table, git log range, gaps),
  version tag | est: 40m |
  verify: `bash build/acceptance_sweep.sh` → all green, zero BLOCKED;
  `uv run pytest -q` → exit 0; `uv run codemonkey --version` matches the tag;
  report updated and committed.
