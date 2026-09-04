# Graph Report - /Users/bharris/Programs/CodeMonkey  (2026-09-02)

## Corpus Check
- Corpus is ~47,834 words - fits in a single context window. You may not need a graph.

## Summary
- 1046 nodes · 2104 edges · 42 communities (38 shown, 4 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 152 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- test_sandbox.py (sandbox.py, can())
- test_verify_gate.py (FallbackRecorded, .__init__()
- test_tools.py (dispatch(), names())
- test_instructions.py (instructions.py, build_proje
- test_retry.py (looks_like_tools_rejection(), retry
- test_approvals.py (approvals.py, decide())
- repomap.py (events.py, emit())
- BUILD_LOG.md (BUILD_LOG.md,  repo scaffold + confi
- test_providers.py (build_provider(), test_provider
- test_repl.py (resolve_api_key(), repl.py)
- openai.py (__init__.py, codemonkey — scriptable co
- test_cycle6.py (test_cycle6.py, _fp_fixture())
- session_state.py (Connection, session_state.py)
- test_protocol.py (ChatTurn, .chat())
- test_prefix_stability.py (test_prefix_stability.py
- cli.py (Argument, command)
- test_exec.py (test_exec.py, FailProvider)
- config.py (config.py, ConfigError)
- __init__.py (get_compactor(), Instantiate a compac
- test_strategies.py (Rolling-summary compaction via
- sessions.py (sessions.py, get_store())
- test_repomap_inject.py (test_repomap_inject.py, _c
- checkpoints.py (checkpoints.py, Checkpoint)
- protocol.py (_native_specs(), native.py)
- cli.py (cli.py, _cfg())
- test_autocompact.py (test_autocompact.py, _big_his
- anthropic.py (AnthropicProvider, ._block_text())
- test_config.py (test_config.py, clean_env())
- test_repomap.py (test_repomap.py, Ctx)
- compaction.py (Keep the last N messages, drop the 
- test_patch_edit.py (test_patch_edit.py, _dispatch(
- AGENTS.md (AGENTS.md, AGENTS.md — operating contra
- SPRINT.md (SPRINT.md, Cycle checklist (mirror of b
- test_hygiene_6f4.py (test_hygiene_6f4.py, _home_se
- test_retry.py (FakeStreamClient, .build_request())
- test_knobs.py (test_knobs.py,  >=3…)
- compaction.py (compaction.py, _estimate_tokens())
- test_strategies.py (cfg(), fixture)
- README.md (README.md, CodeMonkey)
- features.html (features.html, While the home llama
- pyproject.toml (codemonkey)

## God Nodes (most connected - your core abstractions)
1. `run_turns()` - 65 edges
2. `ToolContext` - 57 edges
3. `dispatch()` - 39 edges
4. `ProviderError` - 38 edges
5. `OpenAIProvider` - 31 edges
6. `ChatTurn` - 30 edges
7. `ctx_for()` - 30 edges
8. `AnthropicProvider` - 28 edges
9. `load_config()` - 27 edges
10. `ToolResult` - 27 edges

## Surprising Connections (you probably didn't know these)
- `test_env_override_applied()` --calls--> `load_config()`  [INFERRED]
  tests/test_knobs.py → src/codemonkey/config.py
- `test_unknown_memory_name_exit2()` --calls--> `load_config()`  [INFERRED]
  tests/test_memory_wiring.py → src/codemonkey/config.py
- `test_max_retries_reaches_both_providers()` --calls--> `build_provider()`  [INFERRED]
  tests/test_retry.py → src/codemonkey/providers/__init__.py
- `SpyProvider` --uses--> `ConfigError`  [INFERRED]
  tests/test_memory_wiring.py → src/codemonkey/config.py
- `Turn` --uses--> `ConfigError`  [INFERRED]
  tests/test_memory_wiring.py → src/codemonkey/config.py

## Import Cycles
- None detected.

## Communities (42 total, 4 thin omitted)

### Community 0 - "test_sandbox.py (sandbox.py, can())"
Cohesion: 0.05
Nodes (72): can(), check(), Exception, Sandbox policy for codemonkey tool execution. Three sandbox levels (config…, For path-scoped tools: resolve + ensure inside a root., Raised when a tool call violates the sandbox policy., Coarse gate: is `tool` permitted at `level` at all?, Raise SandboxError if `tool` is not permitted for ctx.sandbox. (+64 more)

### Community 1 - "test_verify_gate.py (FallbackRecorded, .__init__()"
Cohesion: 0.05
Nodes (55): FallbackRecorded, In-memory per-provider prompt-protocol fallback record (auto mode)., Drive the model until a final text answer or max_turns. `approval` (None…, run_turns(), Path, Per-execution context handed to every tool., Absolute, normalized allowed write/read roots (cwd first)., Resolve `path` (abs or cwd-relative) and require it inside a root. (+47 more)

### Community 2 - "test_tools.py (dispatch(), names())"
Cohesion: 0.07
Nodes (51): dispatch(), names(), Execute a tool by name; unknown names / sandbox violations -> ok=False result.…, _ctx_of(), env(), fixture, Cycle 14 (loop2): checkpoints/rollback. Verify probe (plan.md): >=5 tests —…, test_edit_file_snapshots_too() (+43 more)

### Community 3 - "test_instructions.py (instructions.py, build_proje"
Cohesion: 0.06
Nodes (42): build_project_context_block(), find_instructions_file(), load_instructions(), Path, Project-instruction loading (loop4, cycle 18). Loads the project's agent…, Nearest-first walk from workdir up to (and including) the git root. For each…, Load + size-cap instruction text. Disabled or absent -> ""., ONE stable project-context block (cycle 18 + 7F1 groundwork). Order inside the… (+34 more)

### Community 4 - "test_retry.py (looks_like_tools_rejection(), retry"
Cohesion: 0.06
Nodes (46): looks_like_tools_rejection(), annotate(), attempts_for(), backoff_http(), backoff_transport(), do_sleep(), parse_retry_after(), Provider retry policy (loop4, cycle 23). Retry with exponential backoff + FULL… (+38 more)

### Community 5 - "test_approvals.py (approvals.py, decide())"
Cohesion: 0.07
Nodes (38): decide(), Decision, notice_to_stderr(), Approval policy layer (cycle 8). Policies (config `approval` / `--approval`,…, Human-facing notice explaining the gate and how to allow it., Evaluate the approval policy for `tool`., Emit the soft-deny notice on stderr (exec path). `sys.stderr` is resolved at…, The TOOL_RESULT text fed back to the model on a soft-deny. (+30 more)

### Community 6 - "repomap.py (events.py, emit())"
Cohesion: 0.07
Nodes (41): emit(), item_start_sink(), new_thread_id(), JSONL event emitters (codex-style contract, spec §JSONL). stdout purity rule…, Write one event: JSONL line on stdout in json mode, human line to stderr…, Return an on_event callback that maps loop.run_turns events to items. run_turns…, ExecUsageError, find_git_root() (+33 more)

### Community 7 - "BUILD_LOG.md (BUILD_LOG.md,  repo scaffold + confi"
Cohesion: 0.05
Nodes (43): 2026-09-01 — CYCLE 1: repo scaffold + config layer, 2026-09-02 (late tick) — CYCLE 6F1 (review-gate fix): worksp, 2026-09-02 (resumed tick) — CYCLE 6F2 (review-gate fix): exe, 2026-09-02 02:31 — CYCLE 5 in progress (BLOCKED on live endp, 2026-09-02 02:45 — CYCLE 5 live probe strike 2 (server infer, 2026-09-02 03:35 — Tick: CYCLE 5 live strike 3 of 3 → BLOCKE, 2026-09-02 04:06 — Post-BLOCKED tick: server re-check #2, st, 2026-09-02 04:10 — Post-BLOCKED tick: server re-check #3, st (+35 more)

### Community 8 - "test_providers.py (build_provider(), test_provider"
Cohesion: 0.09
Nodes (22): build_provider(), anth_sse(), FakeClient, FakeResp, FakeStream, oai_sse(), Provider-layer tests. All HTTP is mocked (no live network). Covers the cycle-2…, Duck-typed stand-in for httpx.Client for both stream and non-stream. (+14 more)

### Community 9 - "test_repl.py (resolve_api_key(), repl.py)"
Cohesion: 0.10
Nodes (29): resolve_api_key(), _build_provider(), handle_slash(), Interactive REPL (cycle 9). `codemonkey` with no subcommand opens a chat loop:…, Run the interactive/piped REPL. Returns exit code., Best-effort: drop think-tags and leading whitespace., Mutable per-session REPL state (slash commands mutate this)., Handle a slash command; returns "quit", "handled", or "chat". (+21 more)

### Community 10 - "openai.py (__init__.py, codemonkey — scriptable co"
Cohesion: 0.11
Nodes (20): codemonkey — scriptable coding-agent CLI., Agent loop: model -> tool calls -> execute under policy -> feed results.…, _headers(), Anthropic Messages-API provider (Claude). Raw httpx — no SDK. Streaming uses…, AuthError, ProviderBase, ProviderError, Exception (+12 more)

### Community 11 - "test_cycle6.py (test_cycle6.py, _fp_fixture())"
Cohesion: 0.07
Nodes (15): _fp_fixture(), fixture, Cycle 6 unit tests: structured output validation + sessions/resume. No network…, Redirect the sessions dir to a tmp path and bind the module-level `store`…, Patch exec._provider_from_config to return a fresh-typed fake provider., run_exec writes meta+messages for the new thread id., First answer invalid -> one retry turn triggered, retry passes., 6F2: after a schema run with one retry, the persisted thread contains ONLY the… (+7 more)

### Community 12 - "session_state.py (Connection, session_state.py)"
Cohesion: 0.12
Nodes (11): Connection, get_store(), JsonlStore, _path(), Path, Session-state strategies (cycle 7): pluggable backends, config-selected.…, SQLite session store: one row per event, same semantics as jsonl., Instantiate a session store by config name (unknown -> ValueError). (+3 more)

### Community 13 - "test_protocol.py (ChatTurn, .chat())"
Cohesion: 0.10
Nodes (19): ChatTurn, A single model response. `tool_calls` carries native tool calls (provider…, _native_openai_tool_calls(), OpenAI `message.tool_calls` -> [{"name", "args"}, ...]., _call(), ctx(), FakeProvider, fixture (+11 more)

### Community 14 - "test_prefix_stability.py (test_prefix_stability.py"
Cohesion: 0.11
Nodes (22): BadJSONThenGood, _ctx(), MultiTurnProvider, Cycle 22 (loop4): prompt-prefix stability + cache_prompt passthrough. Verify…, The anthropic provider must not gain a cache_prompt field., openai-protocol provider that rejects the `tools` parameter (A9). Records the…, Fails schema validation once, so the schema-retry turn is exercised., Guard against a new provider.chat call site forgetting the flag. (+14 more)

### Community 15 - "cli.py (Argument, command)"
Cohesion: 0.15
Nodes (25): Argument, command, Context, help, is_eager, Option, _callback(), config() (+17 more)

### Community 16 - "test_exec.py (test_exec.py, FailProvider)"
Cohesion: 0.16
Nodes (19): FailProvider, FakeProvider, Cycle 5 unit tests: exec core against a FAKE provider (no network). Live probes…, 6F2: exactly one turn.started per turn.completed (no synthetic extra)., One-turn provider: returns a canned final answer, no tool calls., Run the CLI in-process via CliRunner with a patched provider., run_cli(), test_exec_dash_reads_stdin_as_prompt() (+11 more)

### Community 17 - "config.py (config.py, ConfigError)"
Cohesion: 0.18
Nodes (19): ConfigError, _deep_merge(), _dotenv(), load_config(), _load_yaml(), _parse_scalar(), Exception, Path (+11 more)

### Community 18 - "__init__.py (get_compactor(), Instantiate a compac"
Cohesion: 0.13
Nodes (19): get_compactor(), Instantiate a compaction strategy by config name (unknown -> ValueError)., build(), Strategy registries (cycle 7). Config-selected, env-overridable, pluggable by…, Unknown strategy name (CLI maps this to exit 2)., Resolve the effective strategy name for a domain. Precedence:…, Build the full effective strategy bundle from a config dict. Returns…, select_strategy() (+11 more)

### Community 19 - "test_strategies.py (Rolling-summary compaction via"
Cohesion: 0.14
Nodes (11): Rolling-summary compaction via the active provider (default)., SummarizingCompaction, MockProvider, MockTurn, Cycle 7: pluggable strategy layer — compaction / memory / session state. Covers…, created is stamped once; later append_meta reuses it (floor semantics)., test_both_backends_persist_created_floor(), test_summarizing_falls_back_when_provider_fails() (+3 more)

### Community 20 - "sessions.py (sessions.py, get_store())"
Cohesion: 0.18
Nodes (11): get_store(), _path(), Path, Session persistence + resume (cycle 6 avatar; cycle 7 swaps the backend into…, Cycle 7: route through the strategies registry so the config-selected…, Append-only jsonl session store (default backend)., Earliest `created` from any existing meta event for this thread. First-write…, Returns {meta: {...}, messages: [...]}. Raises FileNotFoundError. (+3 more)

### Community 21 - "test_repomap_inject.py (test_repomap_inject.py, _c"
Cohesion: 0.13
Nodes (9): _ctx(), git_repo(), fixture, Cycle 21 (loop4): repo-map ranking, budget, opt-in injection. Verify probe…, Prefix-stability invariant: the same map text is produced on consecutive turns…, SpyProvider, test_gate_off_by_default_absent(), test_injection_identical_across_two_turns() (+1 more)

### Community 22 - "checkpoints.py (checkpoints.py, Checkpoint)"
Cohesion: 0.20
Nodes (13): Checkpoint, checkpoints_dir(), list_checkpoints(), new_checkpoint(), Path, Checkpoints / rollback (loop2, cycle 14). Before any MUTATING tool (write_file…, One snapshot group: a directory mirroring touched relative paths., Store the PRIOR contents of one file (before mutation). (+5 more)

### Community 23 - "protocol.py (_native_specs(), native.py)"
Cohesion: 0.16
Nodes (15): _native_specs(), openai_tool_result_message(), openai_tool_specs(), Native tool protocol. Feeds provider-native tool calls (OpenAI `tools` /…, {name: one_line_spec} -> OpenAI `tools` array (function type)., Assistant-visible tool result for the prompt-protocol transcript., _extract_json_object(), _missing_call() (+7 more)

### Community 24 - "cli.py (cli.py, _cfg())"
Cohesion: 0.15
Nodes (14): _cfg(), _dispatch_exec_resume(), _ExecTyperGroup, main(), codemonkey CLI entry point (Typer app)., Exec group: `resume` is the ONLY real subcommand. Everything else after the…, Shared tail for exec + exec resume: run_exec with the CLI's exit-code mapping…, `codemonkey exec resume ...` rewrites argv to `codemonkey exec-resume ...`… (+6 more)

### Community 25 - "test_autocompact.py (test_autocompact.py, _big_his"
Cohesion: 0.29
Nodes (13): _big_history(), _ctx(), EchoProvider, Cycle 15 (loop2): auto-compaction in the agent loop. Verify probe (plan.md):…, The exec wiring selects via the registry; env Forces sliding-window., Records what it received; always answers 'ok'., Anti governance-decay: even after compaction the SYSTEM prompt rides every…, test_noop_when_under_budget() (+5 more)

### Community 26 - "anthropic.py (AnthropicProvider, ._block_text())"
Cohesion: 0.21
Nodes (5): AnthropicProvider, Client, Anthropic has no live models-list endpoint on most deployments; fall back to…, Split system out; Anthropic uses a dedicated `system` field. In-prompt `system`…, POST /v1/messages with the shared retry policy. Streaming retries on the…

### Community 27 - "test_config.py (test_config.py, clean_env())"
Cohesion: 0.20
Nodes (13): clean_env(), fixture, Path, run_cli(), test_cli_env_override_shows_in_config(), test_cli_invalid_strategy_exit_2(), test_config_shows_local_defaults(), test_dotenv_in_project_dir() (+5 more)

### Community 28 - "test_repomap.py (test_repomap.py, Ctx)"
Cohesion: 0.16
Nodes (4): Ctx, Cycle 20 (loop4): repo map — def-scan, cache, repo_map tool. Verify probe…, test_repo_map_tool_dispatch(), test_repo_map_tool_pattern_filter()

### Community 29 - "compaction.py (Keep the last N messages, drop the "
Cohesion: 0.18
Nodes (7): Keep the last N messages, drop the rest. No LLM call., SlidingWindowCompaction, Turn, sliding-window must never touch a provider — pass a poison sentinel., test_sliding_window_below_keep_is_noop_copy(), test_sliding_window_drops_old_keeps_last_n(), test_sliding_window_no_llm_call()

### Community 30 - "test_patch_edit.py (test_patch_edit.py, _dispatch("
Cohesion: 0.36
Nodes (9): _dispatch(), Cycle 13 (loop2): search/replace patch editing (SREP blocks in edit_file).…, test_classic_form_still_works(), test_classic_fuzzy_fallback(), test_patch_ambiguous_requires_replace_all(), test_patch_exact_match(), test_patch_fuzzy_whitespace_tolerant(), test_patch_multi_block_all_or_nothing() (+1 more)

### Community 31 - "AGENTS.md (AGENTS.md, AGENTS.md — operating contra"
Cohesion: 0.22
Nodes (8): AGENTS.md — operating contract for any agent working in this, How to create your plan (the framework way), Required reading, in order (before writing your plan), Review-gate discipline (when asked to review or criticize), Stop conditions (you stop and report), What this project is, Working rules when executing a cycle (inherited from SPRINT., graphify — knowledge graph (MANDATORY)

### Community 32 - "SPRINT.md (SPRINT.md, Cycle checklist (mirror of b"
Cohesion: 0.22
Nodes (8): Cycle checklist (mirror of build/plan.md — keep in sync), HARD RULES (never violate), SPRINT — CodeMonkey autonomous build loop, Stop conditions, Ticks (every 5 min), Uncommitted-work rule, Verification methodology, What we're building

### Community 33 - "test_hygiene_6f4.py (test_hygiene_6f4.py, _home_se"
Cohesion: 0.25
Nodes (6): _home_server_inference_alive(), fixture, Cycle 6F4 hygiene-sweep tests (review-gate cycle 6 critic fix cycle). 1. The…, True only if the home llama.cpp actually ANSWERS a chat completion., test_temp_unblock_provider_removed_when_home_serves_inference(), tmp_store()

### Community 35 - "test_knobs.py (test_knobs.py,  >=3…)"
Cohesion: 0.29
Nodes (4): Cycle 17F1: loop-3 knobs as real config knobs. Verify probe (plan.md): >=3…, Patch run_turns inside exec's module and record its kwargs., test_env_override_applied(), test_exec_passes_knobs_to_run_turns()

### Community 36 - "compaction.py (compaction.py, _estimate_tokens())"
Cohesion: 0.40
Nodes (3): _estimate_tokens(), Compaction strategies (cycle 7): pluggable, config-selected. Protocol:…, Cheap char/4 token estimate across all message content strings.

### Community 37 - "test_strategies.py (cfg(), fixture)"
Cohesion: 0.67
Nodes (3): cfg(), fixture, Minimal strategies-only config for registry selection tests.

## Knowledge Gaps
- **62 isolated node(s):** `codemonkey`, `AGENTS.md — operating contract for any agent working in this`, `What this project is`, `Required reading, in order (before writing your plan)`, `How to create your plan (the framework way)` (+57 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ToolContext` connect `test_verify_gate.py (FallbackRecorded, .__init__()` to `test_sandbox.py (sandbox.py, can())`, `test_tools.py (dispatch(), names())`, `test_instructions.py (instructions.py, build_proje`, `test_approvals.py (approvals.py, decide())`, `repomap.py (events.py, emit())`, `test_repl.py (resolve_api_key(), repl.py)`, `openai.py (__init__.py, codemonkey — scriptable co`, `test_protocol.py (ChatTurn, .chat())`, `test_prefix_stability.py (test_prefix_stability.py`, `test_repomap_inject.py (test_repomap_inject.py, _c`, `test_autocompact.py (test_autocompact.py, _big_his`, `test_repomap.py (test_repomap.py, Ctx)`, `compaction.py (Keep the last N messages, drop the `?**
  _High betweenness centrality (0.205) - this node is a cross-community bridge._
- **Why does `run_turns()` connect `test_verify_gate.py (FallbackRecorded, .__init__()` to `test_instructions.py (instructions.py, build_proje`, `test_retry.py (looks_like_tools_rejection(), retry`, `compaction.py (compaction.py, _estimate_tokens())`, `repomap.py (events.py, emit())`, `test_approvals.py (approvals.py, decide())`, `test_repl.py (resolve_api_key(), repl.py)`, `openai.py (__init__.py, codemonkey — scriptable co`, `test_protocol.py (ChatTurn, .chat())`, `test_prefix_stability.py (test_prefix_stability.py`, `test_repomap_inject.py (test_repomap_inject.py, _c`, `protocol.py (_native_specs(), native.py)`, `test_autocompact.py (test_autocompact.py, _big_his`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `ProviderError` connect `openai.py (__init__.py, codemonkey — scriptable co` to `test_retry.py (FakeStreamClient, .build_request())`, `test_retry.py (looks_like_tools_rejection(), retry`, `test_repl.py (resolve_api_key(), repl.py)`, `test_protocol.py (ChatTurn, .chat())`, `test_prefix_stability.py (test_prefix_stability.py`, `test_exec.py (test_exec.py, FailProvider)`, `cli.py (cli.py, _cfg())`, `anthropic.py (AnthropicProvider, ._block_text())`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `run_turns()` (e.g. with `test_env_gate_off_via_config()` and `test_loaded_text_verbatim_in_provider_system()`) actually correct?**
  _`run_turns()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `ToolContext` (e.g. with `ExecUsageError` and `FallbackRecorded`) actually correct?**
  _`ToolContext` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `ProviderError` (e.g. with `AnthropicProvider` and `OpenAIProvider`) actually correct?**
  _`ProviderError` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `OpenAIProvider` (e.g. with `AuthError` and `ChatTurn`) actually correct?**
  _`OpenAIProvider` has 20 INFERRED edges - model-reasoned connections that need verification._