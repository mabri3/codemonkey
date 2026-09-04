# Graph Report - .  (2026-09-04)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1978 nodes · 3692 edges · 115 communities (101 shown, 14 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 246 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4b75ddaf`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_cache_telemetry.py
- test_repl.py
- eval.py
- add
- BUILD_LOG.md
- test_batch_edit.py
- test_r37_fixes.py
- cli.py
- test_retry.py
- test_providers.py
- tools/__init__.py
- ProviderError
- dispatch
- test_cycle6.py
- repomap.py
- test_prefix_stability.py
- eval
- run
- build_digest
- sandbox.py
- run_turns
- load_config
- test_hardening.py
- collect
- SlidingWindowCompaction
- test_exec.py
- test_approvals.py
- read_thread
- checkpoints.py
- run_exec
- test_spill.py
- test_protocol.py
- safe_context_limit
- record
- test_verify_claims.py
- test_instructions.py
- retry.py
- test_strategies.py
- test_graphquery.py
- test_truthpass.py
- test_repomap_inject.py
- run
- compile_corrections
- SummarizingCompaction
- test_checkpoints.py
- pre_apply_validate
- evaluate
- select_route
- run
- test_idempotency.py
- OpenAIProvider
- SqliteStore
- branches.py
- native.py
- validate_root
- test_memory_wiring.py
- test_unload_fallback.py
- test_obsbudget.py
- test_sessions_persist.py
- codemonkey/__init__.py
- validate_args
- test_certify.py
- loop.py
- AnthropicProvider
- test_parallel.py
- test_repomap.py
- test_dry_run.py
- test_exec_robustness.py
- assemble
- test_role_presets.py
- score_rubric
- strategies/__init__.py
- JsonlStore
- test_journal_wiring.py
- test_selfheal.py
- best_of_n
- jobs_cli.py
- create
- load
- gather_diff
- test_slim.py
- test_config.py
- suggest_verify_command
- test_hygiene_6f4.py
- _se
- jobs.py
- AGENTS.md
- SPRINT.md
- approvals.py
- protocol.py
- ChatTurn
- _FakeResp
- NoMemory
- ToolContext
- memory.py
- test_journal_cli.py
- FakeStreamClient
- test_knobs.py
- classify_error
- _native_openai_tool_calls
- test_search_python_fallback_glob_not_regex
- ws
- README.md
- features.html
- test_search_python_fallback_uses_fnmatch
- command
- codemonkey
- ChatTurn
- ProviderBase
- ToolContext
- Client
- Exception
- fixture
- fixture

## God Nodes (most connected - your core abstractions)
1. `run_turns()` - 78 edges
2. `dispatch()` - 50 edges
3. `ToolContext` - 43 edges
4. `ProviderError` - 38 edges
5. `load_config()` - 33 edges
6. `run_exec()` - 33 edges
7. `read_thread()` - 32 edges
8. `ctx_for()` - 30 edges
9. `OpenAIProvider` - 29 edges
10. `record()` - 29 edges

## Surprising Connections (you probably didn't know these)
- `test_unknown_memory_name_exit2()` --calls--> `load_config()`  [INFERRED]
  tests/test_memory_wiring.py → src/codemonkey/config.py
- `test_env_override_applied()` --calls--> `load_config()`  [INFERRED]
  tests/test_knobs.py → src/codemonkey/config.py
- `test_two_edits_on_one_file_both_land()` --calls--> `dispatch()`  [INFERRED]
  tests/test_batch_edit.py → src/codemonkey/tools/__init__.py
- `test_same_file_listed_once_in_the_outcome()` --calls--> `dispatch()`  [INFERRED]
  tests/test_batch_edit.py → src/codemonkey/tools/__init__.py
- `test_second_edit_on_same_file_failing_writes_nothing()` --calls--> `dispatch()`  [INFERRED]
  tests/test_batch_edit.py → src/codemonkey/tools/__init__.py

## Import Cycles
- None detected.

## Communities (115 total, 14 thin omitted)

### Community 0 - "test_cache_telemetry.py"
Cohesion: 0.05
Nodes (45): append_to_ledger(), cache_ratio(), ledger_path(), Path, Token/cost telemetry (loop5, cycle 26). Per-run usage aggregation + a…, Aggregate a JSONL event list (list of dicts) into a cost summary., cached/prompt ratio; None when no prompt tokens or no cache signal., Append a run's summary to the cumulative ledger; returns the ledger. (+37 more)

### Community 1 - "test_repl.py"
Cohesion: 0.07
Nodes (39): _build_provider(), handle_slash(), Interactive REPL (cycle 9). `codemonkey` with no subcommand opens a chat loop:…, Run the interactive/piped REPL. Returns exit code., Best-effort: drop think-tags and leading whitespace., Mutable per-session REPL state (slash commands mutate this)., Handle a slash command; returns "quit", "handled", or "chat"., ReplState (+31 more)

### Community 2 - "eval.py"
Cohesion: 0.07
Nodes (46): batch_by_model(), Model-affinity batching (loop18, cycle 55). Slot swaps cost seconds (page-cache…, Which model slot a task will use (from resolver output if present)., Non-empty contiguous groups, model-affinity ordered, first-appearance group…, route_key(), check_regression(), load_suite(), Path (+38 more)

### Community 3 - "add"
Cohesion: 0.09
Nodes (44): add(), _atomic_write(), lessons_add(), lessons_extract(), lessons_list(), lessons_retrieve(), lessons_verify(), command (+36 more)

### Community 4 - "BUILD_LOG.md"
Cohesion: 0.05
Nodes (43): 2026-09-01 — CYCLE 1: repo scaffold + config layer, 2026-09-02 (late tick) — CYCLE 6F1 (review-gate fix): worksp, 2026-09-02 (resumed tick) — CYCLE 6F2 (review-gate fix): exe, 2026-09-02 02:31 — CYCLE 5 in progress (BLOCKED on live endp, 2026-09-02 02:45 — CYCLE 5 live probe strike 2 (server infer, 2026-09-02 03:35 — Tick: CYCLE 5 live strike 3 of 3 → BLOCKE, 2026-09-02 04:06 — Post-BLOCKED tick: server re-check #2, st, 2026-09-02 04:10 — Post-BLOCKED tick: server re-check #3, st (+35 more)

### Community 5 - "test_batch_edit.py"
Cohesion: 0.08
Nodes (41): fixture, _apply_block(), _exact_search(), _fuzzy_window(), _near_miss_anchors(), parse_blocks(), Search/replace patch editing (loop2, cycle 13). `edit_file` accepts EITHER the…, Apply one block. Returns (new_text, applied_desc, error_msg). (+33 more)

### Community 6 - "test_r37_fixes.py"
Cohesion: 0.07
Nodes (34): adaptive_select(), Adaptive memory management (R35). memory.py (7F1) writes a static file…, Score each line: recency (age of trailing [YYYY-MM-DD] tag, else 0) → decay…, Highest-scoring lines first while under budget (tokens ≈ words)., score_lines(), extract_json(), load_schema_file(), Exception (+26 more)

### Community 7 - "cli.py"
Cohesion: 0.10
Nodes (38): Argument, Context, help, is_eager, Option, _callback(), config(), _dispatch_exec_resume() (+30 more)

### Community 8 - "test_retry.py"
Cohesion: 0.10
Nodes (28): ProviderError, looks_like_tools_rejection(), test_looks_like_tools_rejection(), BoomClient, FakeClient, FakeResp, FakeStreamResp, _provider() (+20 more)

### Community 9 - "test_providers.py"
Cohesion: 0.09
Nodes (21): build_provider(), anth_sse(), FakeClient, FakeResp, FakeStream, oai_sse(), Provider-layer tests. All HTTP is mocked (no live network). Covers the cycle-2…, Duck-typed stand-in for httpx.Client for both stream and non-stream. (+13 more)

### Community 10 - "tools/__init__.py"
Cohesion: 0.12
Nodes (24): Exception, _err(), _load(), Tool base: every tool is `run(args: dict, ctx) -> ToolResult`., ToolResult, glob — find files by pattern, mtime-descending (rg --files -g style)., run(), Tool registry: name -> (run, spec) for prompt-protocol advertising + dispatch. (+16 more)

### Community 11 - "ProviderError"
Cohesion: 0.10
Nodes (22): _headers(), Anthropic Messages-API provider (Claude). Raw httpx — no SDK. Streaming uses…, AuthError, ProviderBase, ProviderError, Exception, Common types and the provider interface., Non-auth provider/transport error. Carries the HTTP status if known. (+14 more)

### Community 12 - "dispatch"
Cohesion: 0.15
Nodes (32): dispatch(), Execute a tool by name; unknown names / sandbox violations -> ok=False result.…, ctx_for(), ToolContext, Tools + sandbox tests (cycle 3). All local; shell tests use safe commands., web_fetch: true config gate (spec:90) — default off, NO network call., test_add_dir_root(), test_edit_file_ambiguous_rejected() (+24 more)

### Community 13 - "test_cycle6.py"
Cohesion: 0.07
Nodes (15): _fp_fixture(), fixture, Cycle 6 unit tests: structured output validation + sessions/resume. No network…, Redirect the sessions dir to a tmp path and bind the module-level `store`…, Patch exec._provider_from_config to return a fresh-typed fake provider., run_exec writes meta+messages for the new thread id., First answer invalid -> one retry turn triggered, retry passes., 6F2: after a schema run with one retry, the persisted thread contains ONLY the… (+7 more)

### Community 14 - "repomap.py"
Cohesion: 0.12
Nodes (28): cache_path(), format_map(), _load_cache(), Path, rank_files(), rank_files_relevant(), Repo map: dependency-free symbol scan (loop4, cycle 20). Scans source files for…, Scan the repo tree -> {relpath: [entries]}. Uses mtime+size cache. (+20 more)

### Community 15 - "test_prefix_stability.py"
Cohesion: 0.11
Nodes (22): BadJSONThenGood, _ctx(), MultiTurnProvider, Cycle 22 (loop4): prompt-prefix stability + cache_prompt passthrough. Verify…, The anthropic provider must not gain a cache_prompt field., openai-protocol provider that rejects the `tools` parameter (A9). Records the…, Fails schema validation once, so the schema-retry turn is exercised., Guard against a new provider.chat call site forgetting the flag. (+14 more)

### Community 16 - "eval"
Cohesion: 0.14
Nodes (25): eval(), Run a golden evaluation suite against the real exec path., Path, Compaction strategy bake-off (loop6, cycle 28). Runs one eval suite once per…, Run the suite once per strategy. Each run gets the strategy env var set for the…, Aligned comparison table across strategies., Delegation ROI: run the suite with delegation OFF vs ON (roles). Arms are…, render_table() (+17 more)

### Community 17 - "run"
Cohesion: 0.10
Nodes (24): ToolResult, delegate — spawn an isolated child codemonkey run (loop9, cycle 37). The…, One child codemonkey run. Returns {ok, output}., run(), _spawn(), ctx(), FakeProc, isolated() (+16 more)

### Community 18 - "build_digest"
Cohesion: 0.13
Nodes (24): build_digest(), digest_cmd(), codemonkey digest (loop21, cycle 58)., Plain-text narrative of one run: tools, failures, flags., digest_recent(), Run digest (loop21, cycle 58): one thread's story in plain text., Digest the N most recent threads (newest first)., render_digest() (+16 more)

### Community 19 - "sandbox.py"
Cohesion: 0.12
Nodes (25): can(), check(), Exception, Sandbox policy for codemonkey tool execution. Three sandbox levels (config…, Raised when a tool call violates the sandbox policy., Coarse gate: is `tool` permitted at `level` at all?, Raise SandboxError if `tool` is not permitted for ctx.sandbox., SandboxError (+17 more)

### Community 20 - "run_turns"
Cohesion: 0.15
Nodes (22): ChatTurn, ProviderBase, FallbackRecorded, In-memory per-provider prompt-protocol fallback record (auto mode)., Drive the model until a final text answer or max_turns. `approval` (None…, run_turns(), _ctx(), Cycle 19 (loop4): verify gate — verification inside the loop. Verify probe… (+14 more)

### Community 21 - "load_config"
Cohesion: 0.13
Nodes (23): _cfg(), ConfigError, _deep_merge(), _dotenv(), load_config(), _load_yaml(), _parse_scalar(), Exception (+15 more)

### Community 22 - "test_hardening.py"
Cohesion: 0.11
Nodes (21): command, Path, Scan journal + eval results for configured API key values and key-shaped…, redact_run(), needles_from_config(), Secret redaction across durable stores (loop16, cycle 49). Hardening pass: eval…, Actual secret values from the config (api_key_env values present in env or…, Replace each needle (and key-shaped strings) with [REDACTED]. Returns… (+13 more)

### Community 23 - "collect"
Cohesion: 0.12
Nodes (23): collect(), collect_latest_sessions(), _cost_section(), _eval_section(), _jobs_section(), _journal_section(), Path, codemonkey status (loop15, cycle 48): operator surface. One-shot aggregation… (+15 more)

### Community 24 - "SlidingWindowCompaction"
Cohesion: 0.16
Nodes (18): Keep the last N messages, drop the rest. No LLM call., SlidingWindowCompaction, _big_history(), _ctx(), EchoProvider, Cycle 15 (loop2): auto-compaction in the agent loop. Verify probe (plan.md):…, The exec wiring selects via the registry; env Forces sliding-window., Records what it received; always answers 'ok'. (+10 more)

### Community 25 - "test_exec.py"
Cohesion: 0.17
Nodes (20): FailProvider, FakeProvider, Cycle 5 unit tests: exec core against a FAKE provider (no network). Live probes…, 6F2: exactly one turn.started per turn.completed (no synthetic extra)., One-turn provider: returns a canned final answer, no tool calls., Run the CLI in-process via CliRunner with a patched provider., run_cli(), test_exec_dash_reads_stdin_as_prompt() (+12 more)

### Community 26 - "test_approvals.py"
Cohesion: 0.14
Nodes (19): decide(), Evaluate the approval policy for `tool`., _ctx(), LoopProvider, Cycle 8: approvals layer + review command. Covers the cycle-8 verify probe…, First turn: try a gated shell call; second turn: final answer., test_approval_never_runs_the_tool(), test_bypass_lifts_approvals() (+11 more)

### Community 27 - "read_thread"
Cohesion: 0.13
Nodes (21): class_summary(), journal_list(), journal_show(), journal_tail(), command, codemonkey journal (loop7, cycle 33): execution-journal forensics., List thread ids that have journals., Show the last N journal records for a thread. (+13 more)

### Community 28 - "checkpoints.py"
Cohesion: 0.15
Nodes (17): begin_call(), Checkpoint, checkpoints_dir(), current_checkpoint(), end_call(), list_checkpoints(), new_checkpoint(), Path (+9 more)

### Community 29 - "run_exec"
Cohesion: 0.14
Nodes (20): resolve_api_key(), emit(), item_start_sink(), new_thread_id(), JSONL event emitters (codex-style contract, spec §JSONL). stdout purity rule…, Write one event: JSONL line on stdout in json mode, human line to stderr…, Return an on_event callback that maps loop.run_turns events to items. run_turns…, ExecUsageError (+12 more)

### Community 30 - "test_spill.py"
Cohesion: 0.14
Nodes (20): prune(), Path, Tool-result spill (loop6, cycle 30). When a tool output exceeds the observation…, Write output verbatim to a spill file; returns its path., Cycle-17-compatible truncation, with a spill pointer when the output exceeds…, Delete spill files older than max_age_hours. Returns count removed., spill(), spill_dir() (+12 more)

### Community 31 - "test_protocol.py"
Cohesion: 0.13
Nodes (12): _call(), ctx(), FakeProvider, fixture, Cycle 4: tool protocol (prompt + native) and the agent loop., Replays scripted responses; raises ProviderError for scripted errors., The A9 mechanic: server 500s on the `tools` param -> prompt protocol,…, test_auto_falls_back_on_tools_rejection() (+4 more)

### Community 32 - "safe_context_limit"
Cohesion: 0.18
Nodes (17): budget_show(), command, codemonkey budget (loop19, cycle 56)., kv_bytes_per_token(), VRAM→tokens budget calculator (loop19, cycle 56). Per-token KV-cache bytes = 2…, Largest context whose KV + weights fit under vram_headroom_gb., render_yaml(), safe_context_limit() (+9 more)

### Community 33 - "record"
Cohesion: 0.16
Nodes (19): args_key(), find_outcome(), journal_dir(), journal_path(), list_threads(), Path, Execution journal (loop7, cycle 31). Append-only per-thread journal at…, Stable idempotency key: thread+run+turn+call-index+canonical args hash. `run`… (+11 more)

### Community 34 - "test_verify_claims.py"
Cohesion: 0.16
Nodes (17): annotate(), check_claims(), _journal_records(), Honest-completion gate (loop17, cycle 52). Fizzbuzz-class defect: the agent…, Audit action claims in reply against journal + filesystem. Returns {claims:…, Run check_claims; if any unverified, append markers to the reply., _tokens(), chome() (+9 more)

### Community 35 - "test_instructions.py"
Cohesion: 0.18
Nodes (17): build_project_context_block(), find_instructions_file(), load_instructions(), Path, Project-instruction loading (loop4, cycle 18). Loads the project's agent…, Nearest-first walk from workdir up to (and including) the git root. For each…, Load + size-cap instruction text. Disabled or absent -> ""., ONE stable project-context block (cycle 18 + 7F1 groundwork). Order inside the… (+9 more)

### Community 36 - "retry.py"
Cohesion: 0.14
Nodes (18): annotate(), attempts_for(), backoff_http(), backoff_transport(), do_sleep(), parse_retry_after(), Provider retry policy (loop4, cycle 23). Retry with exponential backoff + FULL…, True if this HTTP status should be retried (tools-500 excluded). (+10 more)

### Community 37 - "test_strategies.py"
Cohesion: 0.12
Nodes (14): Resolve the effective strategy name for a domain. Precedence:…, select_strategy(), cfg(), fixture, Cycle 7: pluggable strategy layer — compaction / memory / session state. Covers…, created is stamped once; later append_meta reuses it (floor semantics)., Minimal strategies-only config for registry selection tests., sliding-window must never touch a provider — pass a poison sentinel. (+6 more)

### Community 38 - "test_graphquery.py"
Cohesion: 0.17
Nodes (16): find_graph_dir(), graph_query(), load_graph(), Path, Graph-grounded retrieval (R28). The repo ships graphify-out/ for human agents;…, Locate graphify-out/ (or graph.json fallback) relative to workdir., Merge all JSON artifacts into {nodes: {id: node}, edges: [...]}., Pinned nodes whose id/name matches, plus their edges (both ends). (+8 more)

### Community 39 - "test_truthpass.py"
Cohesion: 0.18
Nodes (16): audit_report(), claimed_test_count(), Path, Truth pass (loop 17B, R17B): claims vs evidence over the build ledger. For…, Max 'N/N' pass count attributed to a test file in the report text., fixture, R17B truth pass — claims vs evidence over the build ledger., Truth pass over the ACTUAL repo: every ledger claim has evidence. (+8 more)

### Community 40 - "test_repomap_inject.py"
Cohesion: 0.13
Nodes (9): _ctx(), git_repo(), fixture, Cycle 21 (loop4): repo-map ranking, budget, opt-in injection. Verify probe…, Prefix-stability invariant: the same map text is produced on consecutive turns…, SpyProvider, test_gate_off_by_default_absent(), test_injection_identical_across_two_turns() (+1 more)

### Community 41 - "run"
Cohesion: 0.15
Nodes (15): Path, _save(), write_file — create or overwrite a file (sandbox-gated)., run(), ctx(), fixture, Cycle 37 (loop9): delegate tool — isolated child codemonkey runs., Child exit != 0 propagates as a failed delegate result. (+7 more)

### Community 42 - "compile_corrections"
Cohesion: 0.17
Nodes (14): compile_corrections(), merge_rules(), Corrections compiled into enforcement (R34). Recurring journal failures of the…, (tool, error_class) over threshold → 'ask' rules. Skips tools already covered…, Append drafts that aren't duplicates of current rules., codemonkey rules-compile (R34): journal failures → draft permission rules., Mine journal failure classes into draft ask-rules (drafts need --apply and only…, rules_compile() (+6 more)

### Community 43 - "SummarizingCompaction"
Cohesion: 0.15
Nodes (11): _estimate_tokens(), Compaction strategies (cycle 7): pluggable, config-selected. Protocol:…, Cheap char/4 token estimate across all message content strings., Rolling-summary compaction via the active provider (default)., SummarizingCompaction, MockProvider, MockTurn, test_summarizing_falls_back_when_provider_fails() (+3 more)

### Community 44 - "test_checkpoints.py"
Cohesion: 0.20
Nodes (15): _ctx_of(), Cycle 14 (loop2): checkpoints/rollback. Verify probe (plan.md): >=5 tests —…, Groups written before 14F2 carry no marker and stay eligible., test_batch_edit_makes_one_checkpoint_group(), test_edit_file_snapshots_too(), test_legacy_group_without_workdir_record_still_restores(), test_list_newest_first(), test_new_file_write_makes_no_snapshot() (+7 more)

### Community 45 - "pre_apply_validate"
Cohesion: 0.17
Nodes (14): locate(), pre_apply_validate(), Pre-apply validation + symbol index (R29). Two primitives, both client-side (no…, Syntax-level validation; returns error text or None., {symbol: [relative_path:lineno, ...]} for python files., Definition sites (exact first, then prefix matches, capped)., symbol_index(), R29: pre-apply validation + symbol index. (+6 more)

### Community 46 - "evaluate"
Cohesion: 0.20
Nodes (14): evaluate(), Rule-based tool permissions (loop9, cycle 36). Config `permissions.rules` —…, The string a rule pattern matches against., Returns 'allow' | 'deny' | 'ask' | None (no rule matched). None means "no rules…, _subject(), Cycle 36 (loop9): rule-based permissions., test_allow_first_match_wins(), test_ask_tier() (+6 more)

### Community 47 - "select_route"
Cohesion: 0.17
Nodes (14): Static model routing (loop17, cycle 53). .176 serves 3 models behind one…, Return {provider, model, rule_index or None} for the task., Return an error string for invalid rules, else None., Aggregate eval results per route (per provider/model recorded per task)., route_stats(), select_route(), validate_rules(), Cycle 53 (loop17): static model routing. (+6 more)

### Community 48 - "run"
Cohesion: 0.17
Nodes (14): ToolResult, delegate_batch — parallel fan-out of delegated tasks (loop9, cycle 38). Runs N…, run(), ctx(), fixture, Cycle 38 (loop9): parallel fan-out (delegate_batch)., Results aggregated by index even though workers finish out of order — verified…, One failing task does not kill siblings. (+6 more)

### Community 49 - "test_idempotency.py"
Cohesion: 0.20
Nodes (12): _ctx(), jhome(), fixture, Cycle 32 (loop7): idempotent mutating tools. Verify probe (plan.md): >=5 tests…, Turn 1: write_file call. Turn 2+: final. Counts dispatches via fs., Second run with the same thread + same call: journal outcome replayed, dispatch…, test_miss_executes(), test_readonly_tools_not_replayed() (+4 more)

### Community 50 - "OpenAIProvider"
Cohesion: 0.21
Nodes (7): Client, _auth_headers(), OpenAIProvider, ChatTurn, ProviderBase, Streaming request. Retries apply to the response STATUS only — once bytes have…, test_openai_list_models()

### Community 51 - "SqliteStore"
Cohesion: 0.23
Nodes (3): Connection, SQLite session store: one row per event, same semantics as jsonl., SqliteStore

### Community 52 - "branches.py"
Cohesion: 0.25
Nodes (13): branch_create(), branch_diff(), branch_list(), branch_remove(), _git(), Path, Fork-and-branch execution (R31). `branch_create(name)` → git worktree add…, grepo() (+5 more)

### Community 53 - "native.py"
Cohesion: 0.17
Nodes (14): _native_specs(), Native tool array in the wire shape this provider's protocol expects., anthropic_tool_specs(), openai_tool_result_message(), openai_tool_specs(), Native tool protocol. Feeds provider-native tool calls (OpenAI `tools` /…, Wire schema for one tool, falling back to the registry then to empty. 51F1: an…, {name: one_line_spec} -> OpenAI `tools` array (function type). (+6 more)

### Community 54 - "validate_root"
Cohesion: 0.18
Nodes (11): Path, For path-scoped tools: resolve + ensure inside a root., Absolute, normalized allowed write/read roots (cwd first)., Resolve `path` (abs or cwd-relative) and require it inside a root., validate_root(), repo_map tool (loop4, cycle 20): read-only symbol index of the repo., run(), Path (+3 more)

### Community 55 - "test_memory_wiring.py"
Cohesion: 0.20
Nodes (9): FileMemory, Markdown-file memory store (default)., _ctx(), Cycle 7F1: memory strategy wiring — prompt injection + update_memory tool.…, SpyProvider, test_fact_appears_verbatim_in_system(), test_unknown_memory_name_exit2(), test_update_memory_appends_and_idempotent() (+1 more)

### Community 56 - "test_unload_fallback.py"
Cohesion: 0.16
Nodes (12): fallback_route(), Unload-fallback rerouting (loop18, cycle 54). The LM Studio-class single-slot…, The fallback route applied after an unload failure., _exec_with_unload(), Exception, Cycle 54 (loop18): unload-fallback rerouting., Run real exec; the primary provider raises unloaded on the FIRST chat then…, test_fallback_route_shape() (+4 more)

### Community 57 - "test_obsbudget.py"
Cohesion: 0.25
Nodes (11): _ctx(), Cycle 17 (loop3): observation budget for tool outputs. Verify probe (plan.md):…, One turn: two fat shell outputs (python-generated); then final., call A burns the budget; call B gets ~0 allowance (isolation preserved, both…, _results_of(), test_ledger_shared_across_calls(), test_marker_reports_elided_count(), test_over_budget_truncated_with_partial_marker() (+3 more)

### Community 58 - "test_sessions_persist.py"
Cohesion: 0.27
Nodes (14): _pairs(), _patch_provider(), fixture, CYCLE 7F2 (critic-loop8 finding 1): session persistence is append-only. The…, The history handed to the provider on resume is the stored transcript., Provider returning `answers` in order (last one repeats)., _run(), test_ephemeral_persists_nothing() (+6 more)

### Community 59 - "codemonkey/__init__.py"
Cohesion: 0.14
Nodes (8): parametrize, codemonkey — scriptable coding-agent CLI., Native tool-protocol wire schemas (cycle 50). Regression cover for 51F1:…, The exact 51F1 defect: a tool that takes args advertising none., Guard against schema drift: every declared arg is named in the source., test_declared_properties_match_what_the_tool_reads(), test_no_tool_is_advertised_as_argument_free(), test_required_arguments_are_declared()

### Community 60 - "validate_args"
Cohesion: 0.22
Nodes (12): Tool-argument validation gate (loop20, cycle 57). The 51F1 fix made the wire…, None = valid. Otherwise: {ok: False, error_class: 'schema_mismatch', detail:…, validate_args(), Loop 20 (cycle 57): tool-arg validation gate., The journal contract the loop uses: status=error + error_class=schema_mismatch…, test_classification_roundtrip(), test_missing_required_names_field(), test_non_dict_args() (+4 more)

### Community 61 - "test_certify.py"
Cohesion: 0.22
Nodes (12): m_certificate(), Anytime-valid sequential certificates (R30, Hoeffding-style m-statistics). eval…, After observing ok[i] sequence (1 = pass), is P(pass) > 1/2 certified at level…, Replay outcomes one at a time; return the earliest certificate., sequential_verdict(), R30: anytime-valid sequential certificates., test_all_fail_certifies_false(), test_all_fail_runs_false() (+4 more)

### Community 62 - "loop.py"
Cohesion: 0.23
Nodes (11): preview_diff_edit(), preview_diff_write(), Diff-preview approval mode (R23B). `--approval preview`: before a mutating…, unified_diff(), Agent loop: model -> tool calls -> execute under policy -> feed results.…, R23B: diff-preview approval mode., test_edit_preview_no_change(), test_edit_preview_roundtrip() (+3 more)

### Community 63 - "AnthropicProvider"
Cohesion: 0.21
Nodes (5): AnthropicProvider, Client, Anthropic has no live models-list endpoint on most deployments; fall back to…, Split system out; Anthropic uses a dedicated `system` field. In-prompt `system`…, POST /v1/messages with the shared retry policy. Streaming retries on the…

### Community 64 - "test_parallel.py"
Cohesion: 0.24
Nodes (9): _ctx(), ParallelProvider, Cycle 12 (loop2): parallel tool execution in the agent loop. Verify probe…, One turn with N parallel TOOL_CALL blocks, then a final answer., test_per_call_events(), test_sibling_survives_failure(), test_single_call_still_works(), test_three_call_results_in_call_order() (+1 more)

### Community 65 - "test_repomap.py"
Cohesion: 0.16
Nodes (4): Ctx, Cycle 20 (loop4): repo map — def-scan, cache, repo_map tool. Verify probe…, test_repo_map_tool_dispatch(), test_repo_map_tool_pattern_filter()

### Community 66 - "test_dry_run.py"
Cohesion: 0.19
Nodes (9): preview_for(), Dry-run previews (loop22, cycle 59). exec --dry-run: mutating tool calls return…, Human/model-readable preview of what WOULD execute., Loop 22 (cycle 59): exec --dry-run preview mode., test_edit_preview(), test_journal_preview_record(), test_shell_preview(), test_write_preview() (+1 more)

### Community 67 - "test_exec_robustness.py"
Cohesion: 0.18
Nodes (12): Read piped stdin only when the stream actually has something waiting. select()…, _read_optional_stdin(), Unattended-run robustness (cycle 50). 51F2 — a transport failure printed its…, The exact hang: a writer holds the pipe open and never writes., The feature must survive: `cat notes | codemonkey exec 'summarize'`., CliRunner hands us a StringIO with no fileno; it cannot block., test_idle_open_pipe_returns_empty_instead_of_blocking(), test_in_memory_stream_is_read_directly() (+4 more)

### Community 68 - "assemble"
Cohesion: 0.24
Nodes (11): assemble(), Learned context assembly (R36). Assembly as scoring, not a fixed recipe:…, fragments: [{source, text}]. Greedy fill by utility; keeps original selection…, _recency_weight(), _terms(), R36: learned context assembly., test_budget_drop_uses_utility(), test_empty_fragments() (+3 more)

### Community 69 - "test_role_presets.py"
Cohesion: 0.22
Nodes (11): apply_to_cmd(), Delegate role presets (loop24, cycle 61). role_presets config: role →…, {provider, model, preset: name-or-''}., Overlay resolved provider/model into a delegate CLI arg dict., resolve_role_preset(), Loop 24 (cycle 61): delegate role presets., test_apply_overlays_cmd_args(), test_empty_config_no_change() (+3 more)

### Community 70 - "score_rubric"
Cohesion: 0.23
Nodes (11): Step-level scoring + rubrics (R33, generative-verifier substrate). A rubric =…, rubric steps: {"id", "kind": contains|regex|absent, "value"}. Returns {steps:…, Authoring sugar: ["contains: hello", "regex: \\d+"] → structured., rubric_from_yaml_steps(), score_rubric(), R33: rubrics + step-level scoring., test_absent_semantics(), test_all_steps_pass() (+3 more)

### Community 71 - "strategies/__init__.py"
Cohesion: 0.21
Nodes (12): get_compactor(), Instantiate a compaction strategy by config name (unknown -> ValueError)., build(), Strategy registries (cycle 7). Config-selected, env-overridable, pluggable by…, Unknown strategy name (CLI maps this to exit 2)., Build the full effective strategy bundle from a config dict. Returns…, StrategyError, get_store() (+4 more)

### Community 72 - "JsonlStore"
Cohesion: 0.24
Nodes (6): JsonlStore, _path(), Path, Session-state strategies (cycle 7): pluggable backends, config-selected.…, Append-only JSONL session store (default backend)., sessions_dir()

### Community 73 - "test_journal_wiring.py"
Cohesion: 0.23
Nodes (12): _exec_once(), _patch_tool_provider(), CYCLE 31F1 (critic-loop8 finding 2): the execution journal is wired. Before…, eval derives the journal thread from the run's own thread.started., The REPL is wired too (piped-stdin mode drives one turn)., exec provider that calls one tool, then answers., Two invocations on ONE thread must not replay each other's writes., test_eval_results_carry_journal_stats() (+4 more)

### Community 74 - "test_selfheal.py"
Cohesion: 0.23
Nodes (9): _ctx(), EditFlakyProvider, Cycle 16 (loop3): self-heal edit retries. Verify probe (plan.md): >=4 tests —…, Turn 1: bad edit (SEARCH text absent). Turn 2: reads, corrected edit. Turn 3:…, test_no_retry_when_edit_ok(), test_non_edit_failures_do_not_retry(), test_retry_after_edit_failure(), test_retry_limit_respected() (+1 more)

### Community 75 - "best_of_n"
Cohesion: 0.24
Nodes (10): best_of_n(), Best-of-N with an execution verifier (R32). Generate N candidate completions…, Run the machine verifier; (passed, output-tail)., Score candidates in order; pick the first whose application passes verify.…, score_with_verifier(), R32: best-of-N with an execution verifier., test_first_passing_candidate_wins(), test_none_pass_returns_evidence() (+2 more)

### Community 76 - "jobs_cli.py"
Cohesion: 0.27
Nodes (11): jobs_create(), jobs_done(), jobs_fail(), jobs_list(), jobs_show(), command, codemonkey jobs (loop12, cycle 43): durable task files., Human-readable render — also the injection text for exec --job. (+3 more)

### Community 77 - "create"
Cohesion: 0.24
Nodes (11): create(), jhome(), fixture, Cycle 43 (loop12): durable jobs module + CLI., subprocess_run(), test_cli_jobs_flow(), test_create_and_show(), test_done_and_fail_statuses() (+3 more)

### Community 78 - "load"
Cohesion: 0.26
Nodes (9): load(), Cycle 44 (loop12): exec --job injection + JOB_STEP write-back., Run the real exec path with a stubbed loop (no live model)., _run_exec(), test_cross_run_resume_shows_progress(), test_ephemeral_does_not_write(), test_invalid_marker_ignored(), test_job_injection_and_persist() (+1 more)

### Community 79 - "gather_diff"
Cohesion: 0.24
Nodes (11): gather_diff(), git_out(), Path, `codemonkey review` (cycle 8): LLM code review of uncommitted diffs. Gathers a…, Unified diff context: uncommitted (working tree vs HEAD) or vs base., Gather the diff and run one review turn. Returns the review text., run_review(), test_review_diff_gather_uncommitted() (+3 more)

### Community 80 - "test_slim.py"
Cohesion: 0.24
Nodes (10): Tool-output slimming (loop8, cycle 35). Deterministic, LLM-free noise reduction…, Slim an output string. Outputs under min_chars pass untouched., slim(), Cycle 35 (loop8): tool-output slimming., test_ansi_strip(), test_blank_line_collapse(), test_no_noise_no_saving(), test_slim_stat_is_journaled() (+2 more)

### Community 81 - "test_config.py"
Cohesion: 0.24
Nodes (11): clean_env(), fixture, Path, run_cli(), test_cli_env_override_shows_in_config(), test_cli_invalid_strategy_exit_2(), test_config_shows_local_defaults(), test_dotenv_in_project_dir() (+3 more)

### Community 82 - "suggest_verify_command"
Cohesion: 0.25
Nodes (9): verify-gate auto-suggestion (loop26, cycle 63). If the run exercised pytest and…, Return the suggestion text, or None (used already / not applicable)., suggest_verify_command(), Loop 26 (cycle 63): verify-gate auto-suggestion., The suggestion is deterministic — same inputs, same text., test_no_suggestion_without_pytest(), test_silent_when_configured(), test_suggestion_object_stable() (+1 more)

### Community 83 - "test_hygiene_6f4.py"
Cohesion: 0.22
Nodes (8): _home_reachable(), _home_server_inference_alive(), fixture, Cycle 6F4 hygiene-sweep tests (review-gate cycle 6 critic fix cycle). 1. The…, True only if the home llama.cpp actually ANSWERS a chat completion., True if the home server accepts connections at all (TCP level)., test_temp_unblock_provider_removed_when_home_serves_inference(), tmp_store()

### Community 84 - "_se"
Cohesion: 0.22
Nodes (8): _ctx(), config gate off -> text absent from the system prompt., Simulate exec's system_extra construction for the gate., _se(), SpyProvider, test_env_gate_off_via_config(), test_loaded_text_verbatim_in_provider_system(), Turn

### Community 85 - "jobs.py"
Cohesion: 0.33
Nodes (9): _atomic_write(), job_path(), jobs_dir(), list_jobs(), Path, Durable job files (loop12, cycle 43). Workflow state ≠ session state: a job is…, save(), Atomicity: tmp+replace means the job file is never partially written. Simulate:… (+1 more)

### Community 86 - "AGENTS.md"
Cohesion: 0.22
Nodes (8): AGENTS.md — operating contract for any agent working in this, How to create your plan (the framework way), Required reading, in order (before writing your plan), Review-gate discipline (when asked to review or criticize), Stop conditions (you stop and report), What this project is, Working rules when executing a cycle (inherited from SPRINT., graphify — knowledge graph (MANDATORY)

### Community 87 - "SPRINT.md"
Cohesion: 0.22
Nodes (8): Cycle checklist (mirror of build/plan.md — keep in sync), HARD RULES (never violate), SPRINT — CodeMonkey autonomous build loop, Stop conditions, Ticks (every 5 min), Uncommitted-work rule, Verification methodology, What we're building

### Community 88 - "approvals.py"
Cohesion: 0.28
Nodes (7): Decision, notice_to_stderr(), Approval policy layer (cycle 8). Policies (config `approval` / `--approval`,…, Human-facing notice explaining the gate and how to allow it., Emit the soft-deny notice on stderr (exec path). `sys.stderr` is resolved at…, The TOOL_RESULT text fed back to the model on a soft-deny., tool_result_notice()

### Community 89 - "protocol.py"
Cohesion: 0.39
Nodes (8): _extract_json_object(), _missing_call(), _parse_lines(), _parse_one(), parse_tool_calls(), Prompt tool protocol: `TOOL_CALL: {"name": ..., "arguments": {...}}` in text.…, Return the first balanced top-level JSON object in `text`, or "". models append…, Parse `text` into (calls, prose). calls: list of {"name", "args", "error"?}…

### Community 90 - "ChatTurn"
Cohesion: 0.25
Nodes (5): ChatTurn, A single model response. `tool_calls` carries native tool calls (provider…, ReviewProvider, test_chatturn_defaults(), TokenSink

### Community 92 - "NoMemory"
Cohesion: 0.25
Nodes (5): prompt_block(), Build the tool-advertising block for the system prompt. `specs` is the {name:…, NoMemory, Memory disabled: load() -> "", add_fact() is a no-op., test_memory_none_hides_fact_and_tool()

### Community 93 - "ToolContext"
Cohesion: 0.29
Nodes (4): Per-execution context handed to every tool., ToolContext, Ctx, Turn

### Community 94 - "memory.py"
Cohesion: 0.32
Nodes (6): get_memory(), _memory_path(), Path, Memory strategies (cycle 7): pluggable, config-selected. Protocol: load() ->…, Instantiate a memory strategy by config name (unknown -> ValueError)., test_get_memory_none_returns_nomemory()

### Community 95 - "test_journal_cli.py"
Cohesion: 0.29
Nodes (7): jhome(), fixture, Cycle 33 (loop7): journal forensics CLI., _run_cli(), test_cli_list_and_show(), test_show_missing_thread_errors(), test_tail_shape()

### Community 97 - "test_knobs.py"
Cohesion: 0.29
Nodes (4): Cycle 17F1: loop-3 knobs as real config knobs. Verify probe (plan.md): >=3…, Patch run_turns inside exec's module and record its kwargs., test_env_override_applied(), test_exec_passes_knobs_to_run_turns()

### Community 98 - "classify_error"
Cohesion: 0.50
Nodes (4): BaseException, classify_error(), Map an exception to the fixed error-class enum., test_error_classes()

### Community 99 - "_native_openai_tool_calls"
Cohesion: 0.50
Nodes (4): _native_openai_tool_calls(), OpenAI `message.tool_calls` -> [{"name", "args"}, ...]., test_native_openai_tool_call_bad_json_preserved(), test_native_openai_tool_call_extraction()

### Community 100 - "test_search_python_fallback_glob_not_regex"
Cohesion: 0.33
Nodes (4): names(), A pattern valid as glob but invalid as regex must not crash the fallback., test_registry_has_all_thirteen(), test_search_python_fallback_glob_not_regex()

### Community 101 - "ws"
Cohesion: 0.67
Nodes (3): fixture, Workspace with a couple of files; ctx defaults to workspace-write., ws()

## Knowledge Gaps
- **62 isolated node(s):** `AGENTS.md — operating contract for any agent working in this`, `What this project is`, `Required reading, in order (before writing your plan)`, `How to create your plan (the framework way)`, `Working rules when executing a cycle (inherited from SPRINT.` (+57 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_turns()` connect `run_turns` to `test_repl.py`, `test_batch_edit.py`, `test_r37_fixes.py`, `test_retry.py`, `test_prefix_stability.py`, `SlidingWindowCompaction`, `test_approvals.py`, `read_thread`, `run_exec`, `test_spill.py`, `test_protocol.py`, `test_repomap_inject.py`, `SummarizingCompaction`, `test_idempotency.py`, `native.py`, `test_memory_wiring.py`, `test_obsbudget.py`, `validate_args`, `loop.py`, `test_parallel.py`, `test_dry_run.py`, `test_selfheal.py`, `test_slim.py`, `_se`, `protocol.py`, `NoMemory`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Why does `run_exec()` connect `run_exec` to `test_cache_telemetry.py`, `test_repl.py`, `eval.py`, `test_verify_claims.py`, `test_exec_robustness.py`, `test_instructions.py`, `test_r37_fixes.py`, `cli.py`, `repomap.py`, `select_route`, `eval`, `suggest_verify_command`, `run_turns`, `load_config`?**
  _High betweenness centrality (0.131) - this node is a cross-community bridge._
- **Why does `load_config()` connect `load_config` to `test_knobs.py`, `cli.py`, `compile_corrections`, `run`, `test_config.py`, `test_hardening.py`, `test_memory_wiring.py`, `run_exec`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `run_turns()` (e.g. with `truncate_with_spill()` and `_estimate_tokens()`) actually correct?**
  _`run_turns()` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `dispatch()` (e.g. with `check()` and `test_later_edit_sees_the_earlier_edit_text()`) actually correct?**
  _`dispatch()` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `ToolContext` (e.g. with `LoopProvider` and `ReviewProvider`) actually correct?**
  _`ToolContext` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `ProviderError` (e.g. with `AnthropicProvider` and `FailProvider`) actually correct?**
  _`ProviderError` has 22 INFERRED edges - model-reasoned connections that need verification._