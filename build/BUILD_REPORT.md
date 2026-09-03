# BUILD_REPORT — Loop 1 Final Acceptance (Cycle 10)

**Date:** 2026-09-02 · **Repo:** ~/Programs/CodeMonkey · **Suite:** 164/164 passed
**Live provider used for LLM probes:** `unblock2` (127.0.0.1:3459, kimi-k2.7-code) — the
home llama.cpp server (192.168.50.113:8080) `/v1/models` answers but inference is wedged
(POST /chat/completions times out); probes A4/A5/A6/A7/A9/A10/A11/A16 therefore ran live
against unblock2. The prompt-tool-protocol path (A9) exercised the real parser→sandbox→
shell→feedback loop; the llama.cpp-specific `tools`-param 500→prompt-fallback (A9 mechanic
from cycle 4) is covered by its unit tests against the recorded 500 behavior.

## Acceptance criteria — all 20 PASS

| # | Probe (spec.md literal) | Result |
|---|---|---|
| A1 | `codemonkey --version` → `codemonkey 0.1.0`, exit 0 | ✅ |
| A2 | `config` shows local provider, llama.cpp URL, GGUF model; no `sk-` secrets | ✅ exit 0 |
| A3 | `CODEMONKEY_MODEL=override-test` env override visible in config | ✅ exit 0 |
| A4 | `models` live listing | ✅ (local wedged → unblock2 fallback, exit 0) |
| A5 | `exec "…pong"` → stdout `pong` | ✅ exit 0 |
| A6 | `exec --json` → JSONL with thread.started + turn.completed | ✅ 5 lines, 4 types |
| A7 | stdin-as-prompt (`exec -`) → `banana` | ✅ exit 0 |
| A8 | non-git dir guard → exit 2, mentions git repo + --skip-git-repo-check | ✅ |
| A9 | tool loop end-to-end: shell `echo codemonkey_tool_test` | ✅ exit 0, output returned |
| A10 | `--output-schema` + `--output-last-message` → valid JSON (project_name, languages) | ✅ parsed OK |
| A11 | resume: token word `zebra` remembered across threads | ✅ exit 0 |
| A12 | `sessions` lists the A11 thread | ✅ exit 0 |
| A13 | `CODEMONKEY_PROVIDER=anthropic` → protocol: anthropic | ✅ exit 0 |
| A14 | provider unit tests (13) | ✅ 13 passed |
| A15 | full suite | ✅ 164 passed |
| A16 | `review --uncommitted` live → ≥400 chars | ✅ 3087 chars + verdict |
| A17 | sandbox unit tests (read-only denies write+shell) | ✅ 13 passed |
| A18 | `--help` lists exec/review/sessions/config/models | ✅ |
| A19 | strategy selector: env override exit 0; bogus name exit 2 + valid names | ✅ |
| A20 | strategy unit tests: jsonl+sqlite round-trip, sliding-window | ✅ 18 passed |

Literal probe output: `build/acceptance_outputs/` (a1..a20 .out/.err + summary.txt).

## Fixes made during the sweep

1. **Protocol robustness (real bug):** models append special tokens after the tool-call
   JSON (`…} <|tool_call_end|>` from kimi-k2.7) → strict `json.loads` failed and the
   shell tool never ran. `protocol._parse_one` now falls back to extracting the first
   balanced `{…}` object (string/escape-aware brace walk). Regression-tested + live A9.
2. **`--approval` flag alias (real bug):** spec probes use `--approval never`; exec only
   accepted `--ask-for-approval` and `exec`'s `ignore_unknown_options` silently ate the
   unknown flag → approval gate never lifted. Added `--approval` alias to exec,
   exec resume, exec-resume alias, and the REPL callback.
3. **`sessions` rich contract (cycle-7 regression):** registry stores' `list()` returned
   bare {thread_id, created, updated}; CLI expects provider/model/n_messages/
   first_prompt/cwd (cycle-6 contract). Unified in `strategies/session_state.py` for
   both jsonl + sqlite; `latest()` aligned newest-first.
4. Sweep-script fixes: A4 local-wedged fallback note; A17 grep asserts against the
   actual denial wording.

## Known gaps / notes

- Home llama.cpp inference wedge persists (~2 days). All live-LLM criteria were
  proven live via the 3459 unblock2 provider; the guard test (6F4) still enforces
  removal of both TEMP providers the moment home inference recovers.
- `codemonkey review` A16 verified live (3,087 chars, verdict); re-run against home
  server when it recovers for spec-literal parity.
- Cron build-loop (`ce0f0b87a18c`) remains stalled on the Hermes gateway runtime
  (`tool_call_id` TypeError in stale in-memory code); all cycle-7..10 work was done
  in the interactive session. External `hermes gateway restart` still recommended.

## Git range

Loop-1 cycles this report covers: `6528806` (cycle 1) … cycle 10 (this commit).
Key commits since the last report: `220f69d` C4, `e8e3bae` C5, `29629ad` C6,
`e609ba8` review gate, `2a51f38`/`c572f82`/`6863814`/`833cffa` 6F1–6F4,
`37345aa` C7, `05debfb` C8, `5492dbe` C9, this commit C10.

**Loop 1 COMPLETE — proceeding to CYCLE 11 (loop 2 research) per the signed
autonomous-build contract; next user review point is after loop 3.**


---

# Loop 2 — Final Acceptance (CYCLE loop2-final)

**Date:** 2026-09-02 · **Suite:** 189/189 · **Re-sweep:** all A1–A20 exit 0 (same
probe wall as loop 1; A4 unblock2 fallback note unchanged; A9 live with the new
trailing-token-tolerant parser — model-special-tokens handled; A16 live review
2,573 chars).

## Loop-2 criteria (from build/research-loop2.md — all pass)

| Improvement | Probe | Result |
|---|---|---|
| Parallel tool execution | tests/test_parallel.py: 3 slow calls finish < serial; call-order results; per-call events; sibling isolation | ✅ 5/5 (+ live 3-call one-turn probe: "alpha beta gamma") |
| SREP patch editing | tests/test_patch_edit.py: exact/fuzzy/anchors/atomicity/multi-block | ✅ 8/8 (+ live SREP patch applied to a fresh repo) |
| Checkpoints/rollback | tests/test_checkpoints.py: prior-content snapshot, byte-identical restore, ordering, no-snapshot-for-new-files | ✅ 6/6 (+ live clobber→`codemonkey undo` → byte-identical) |
| Auto-compaction | tests/test_autocompact.py: trigger/no-op/system re-injection/notice/registry selection/summarizing flow | ✅ 6/6 (+ in-process 25→11 message compaction with marker) |

## Loop-2 commits

`8d40ebb` (research) → `bc15fdd` (parallel) → `12db920` (patch edit) →
`6a2123d` (checkpoints) → `9f4eb67` (auto-compaction) → this commit (loop2-final).

## Loop-2 notes

- Selected-but-deferred (recorded in research-loop2.md): MCP-style extension
  points (surface area > core-loop leverage for a 27B local model) and agentic
  self-review (2x token cost per headless run).
- `strategies.compaction_keep` knob added (was hardcoded 10).
- Anti-governance-decay invariant enforced: post-compaction turns always carry
  exactly one deduped `[prior context]` brief + the full system prompt.

**Loop 2 COMPLETE — proceeding to CYCLE R3 (loop 3 research).**


---

# Loop 3 — FINAL ACCEPTANCE (CYCLE loop3-final) — USER GATE 2 REQUESTED

**Date:** 2026-09-02 · **Suite:** 197/197 · **Re-sweep:** all A1–A20 exit 0
(A4 via unblock2 fallback note; A16 live review 2,622 chars; A9 tool loop live).
Probe wall: `build/acceptance_outputs/`.

## Loop-3 criteria (from build/research-loop3.md — all pass)

| Improvement | Probe | Result |
|---|---|---|
| Self-heal edit retries | tests/test_selfheal.py: feedback delivered, success-after-retry, no-retry on success, limit respected | ✅ 4/4 (+ live: forced bad SEARCH → self-heal → correct rename, DONE-RECOVERED) |
| Observation budget | tests/test_obsbudget.py: marker format, elided count, shared ledger, under-budget untouched | ✅ 4/4 (+ live bridge + PARTIAL at 5k budget) |
| Native→prompt bridge (bonus bug fix) | live: kimi/3459 wraps TOOL_CALL in content during native mode; previously returned as final answer, tool never ran | ✅ notice + tool executes + BUDGET-OK |

## Complete run summary — all three loops

- **Loop 1 (cycles 1–10):** scaffold/config → providers → tools/sandbox →
  protocol/loop → exec → structured output/sessions (+review-gate fixes 6F1–6F4)
  → strategies → approvals/review → REPL → acceptance sweep. **All A1–A20.**
- **Loop 2 (11–15 + final):** research → parallel tool execution → SREP patch
  editing → checkpoints/undo → auto-compaction → re-sweep green.
- **Loop 3 (R3, 16–17 + final):** research → self-heal edit retries → observation
  budget (+ native→prompt bridge bug fix) → re-sweep green.

**Commit range:** `6528806` (cycle 1) … `e1788fb` (cycle 17).
Full chain: 220f69d C4 · e8e3bae C5 · 29629ad C6 · e609ba8 review gate ·
2a51f38/c572f82/6863814/833cffa 6F1–F4 · 37345aa C7 · 05debfb C8 · 5492dbe C9 ·
2531b11 C10 · 8d40ebb C11 · bc15fdd C12 · 12db920 C13 · 6a2123d C14 · 9f4eb67 C15 ·
1ee1457 loop2-final · 1e2b23a R3 · afb9f3c C16 · e1788fb C17 · this commit.

## Environment notes (unchanged)

- Live-LLM probes ran against the TEMP `unblock2` provider (3459/kimi) — home
  llama.cpp inference still wedged; the 6F4 guard test removes TEMP providers
  automatically the moment home serves inference.
- Cron build-loop stayed gateway-stalled all run (`tool_call_id` stale-runtime
  bug); every cycle was executed and committed from the interactive session.

## ⚠️ USER ACCEPTANCE REQUESTED (Gate 2)

This is the end of the autonomous run per the signed contract
(`cap: none`, stop = loop3-final acceptance passing). **codemonkey is built:**
a multi-provider (OpenAI/Anthropic wire), prompt-or-native tool-protocol,
strategy-pluggable (compaction/memory/session-state), sandboxed, approvals-aware,
checkpointing, self-healing, budget-managing, scriptable + interactive coding-agent
CLI — 197 tests green, all 20 original acceptance criteria + 8 loop-2/3 improvement
probes passing live.

Please review: `git -C ~/Programs/CodeMonkey log --oneline`, `features.html`,
`build/BUILD_REPORT.md`. Accept, or list deficiencies and the loop continues.


---

# Loop 4 — Final Acceptance (CYCLE loop4-final)

**Date:** 2026-09-02 · **Suite:** 271/271 · **Re-sweep:** all A1–A20 exit 0 —
**A4 ran LIVE against the home llama.cpp server (unblock2 fallback NOT used:
the home server recovered during this loop)**.

## Loop-4 criteria (from build/research-loop4.md — all pass)

| Improvement | Probe | Result |
|---|---|---|
| Project-instruction loader | tests/test_instructions.py: discovery precedence, nearest-dir wins, 32KB cap+marker, gates | ✅ 10/10 (+ live pineapple both directions) |
| Verify gate | tests/test_verify_gate.py: unset never runs; failure feeds corrective turn; pass adds none; retry cap; budget-charged; event order | ✅ 6/6 (+ live break-fix probe: GATE-OK) |
| Repo map (part 1) | tests/test_repomap.py: 7-language def-scan, mtime+size cache, ignore dirs, deterministic limit, binary skip | ✅ 9/9 |
| Repo map (part 2) | tests/test_repomap_inject.py: recency+density ranking, budget never exceeded, gate-off absent, identical across turns | ✅ 7/7 (+ live: protocol.py named, zero read_file) |
| Memory wiring (7F1) | tests/test_memory_wiring.py: fact verbatim in system; none hides fact+tool; idempotent update_memory | ✅ 6/6 (+ live token recall) |
| Config knobs (17F1) | tests/test_knobs.py: defaults, env override, exec pass-through | ✅ 4/4 |
| Prompt-prefix stability + cache_prompt (22) | tests/test_prefix_stability.py: byte-identical system across turns & compaction; body flag present/absent; anthropic untouched | ✅ 6/6 (+ best-effort timings recorded, no claim) |
| Provider retry/backoff (23) | tests/test_retry.py: Retry-After exact, bounded jitter, no 4xx retry, AuthError immediate, tools-500 immediate (fallback intact), exhaustion count | ✅ 9/9 |
| Critic fixes 19F1 / 22F1 | real exit codes in verify.completed; cache_prompt on all 7 chat sites | ✅ |

## Hygiene: TEMP providers removed (the 6F4 guard fired for real)

The home llama.cpp server recovered during this loop. The 6F4 guard's alive-probe
had a blind spot (8-token budget → empty content on a reasoning model → read as
"dead"); fixed (200-token probe), then BOTH temp providers (`unblock` 3458,
`unblock2` 3459) removed from DEFAULTS in the same commit. All live probes now
run against the home server. Config default_provider returned to `local`.

## Loop-4 commit range

`18301af` (R4 research) → 2b08b34 (approval) → 008f289 C18 → 389b8fa C19 →
d0fade9 C20 → 0f6f12a 7F1 → 654ece6 17F1 → 2e5fb21 C21 → 9adcb7a C22 →
16c27bf C23 → dd4a329 19F1 → 8b6c56a 22F1 → af7d047 critic report + charters →
206c431 graphify mandate → this commit (loop4-final + hygiene).

## Notes

- graphify knowledge graph mandated (AGENTS.md) and built: 1046 nodes/2104 edges;
  per-cycle `--update` now part of the ritual.
- Loops 5–10 charters remain PROPOSED, research-gated (see plan.md).


---

# Loop 5 — Final Acceptance (CYCLE loop5-final)

**Date:** 2026-09-02 · **Suite:** 292/292 · **Re-sweep:** 19/20 criteria exit 0,
13 of them **live on the home llama.cpp server**. A9 (tool-loop probe) is
BLOCKED-slow on the local 27B hardware: the reasoning model cannot finish the
4-completion loop inside 240s/stream. It passed live twice earlier (loop-1 and
loop-4 sweeps) and the code path is unchanged since + unit-covered — recorded
honestly in `build/acceptance_outputs/summary.txt`.

## Loop-5 criteria (from build/research-loop5.md — all pass)

| Improvement | Probe | Result |
|---|---|---|
| Eval harness core (24) | tests/test_eval.py: YAML load+malformed reject, patched-exec run, stdout contract, trajectory subset-in-order, results.json | ✅ 6/6 (+ live 2-task smoke: pass_rate 1.0) |
| Golden suite + baseline (25) | tests/test_golden.py: baseline roundtrip, regression detected, improvement never fails, no-baseline ok, live CLI --check exit-1 flow | ✅ 5/5 |
| Cost telemetry (26) | tests/test_cost.py: summarize totals, ledger cumulative, render shape, no-tools, live --cost-summary e2e | ✅ 5/5 |
| Repo-map relevance (27) | tests/test_repomap_relevance.py: relevance overrides recency (git fixture), non-matching fallback, score counts, budget enforced, deterministic | ✅ 5/5 |

## Real bugs fixed this loop

1. **exec event_sink gap** (cycle 24): `emit()` never fed external collectors —
   item.completed events invisible to any external observer.
2. **write_baseline shadowing** (cycle 25): CLI param shadowed by same-named
   import; truthy function object made EVERY run write baseline and skip the
   regression check — the gate would never have fired.
3. **Streaming wedge** (loop5-final): httpx read-timeout only fires on gaps
   BETWEEN stream bytes; a reasoning model trickling tokens never trips it
   (A9 hung the sweep 31+ min). Added a wall-clock deadline guard per stream.
4. **Sweep staleness**: sweep still hardcoded the removed unblock2 provider —
   now home-first with honest fallback.

## Loop-5 commit range

f936f5d (R5) → 28938b0 C24 → f23d43d C25 → 6edfe13 docs → 185f368 C26 →
90c6aa4 C27 → this commit (loop5-final).

## Notes

- The R5 core-design questions remain OPEN for the user: subagents/delegated
  context isolation; hooks/rule-based command permissions.
- R6 entry condition (eval harness scoring two configurations) is SATISFIED by
  cycles 24/25.


---

# Loop 7 — Final Acceptance (CYCLE loop7-final)

**Date:** 2026-09-02 · **Suite:** 324/324 (4 live-probe tests skipped: home
llama.cpp flapped DOWN mid-loop — connect-timeout; honest skip via
tests/conftest.py `requires_home`, per the loop5-final environment precedent).
The sweep's fallback path (record-honestly) applies for A-probes; the loop-7
journal/idempotency/forensics contracts are fully unit-verified.

## Loop-7 criteria (from build/research-loop7.md — all pass)

| Improvement | Probe | Result |
|---|---|---|
| Execution journal + failure taxonomy (31) | tests/test_journal.py: intent-before-outcome, error-class enum, args never on disk (hash only), kill-safety, thread isolation, loop end-to-end | ✅ 8/8 |
| Idempotent mutating tools (32) | tests/test_idempotency.py: replay-on-hit (mtime unchanged), miss executes, read-only unaffected, key stability/distinction, replay journaled | ✅ 5/5 |
| Journal forensics (33) | tests/test_journal_cli.py: list/tail/show, class summary, eval hook | ✅ 5/5 |

## Real bugs fixed this loop

1. **Missing `import time`** in loop.py (journal duration instrumentation) —
   33 test failures traced to one NameError.
2. **6F4 guard vs flapping server**: when home is network-unreachable the
   hygiene decision is undecidable — guard now skips instead of failing on an
   environment condition (hygiene action itself was already verified in
   loop4-final).

## Loop-7 commit range

edbe818 (R7) → 70e5117 C31 → 946437c C32 → 735c06f C33 → this commit
(loop7-final).

## Notes

- Session-state strategy contract UNTOUCHED (journal is a sidecar) — the R7
  core-design flag was avoided by design.
- Mid-turn crash resume deliberately deferred: the journal (this loop) is its
  prerequisite; R8 opens next (throughput/cost), with measured cache/depth
  data from loops 5-6.
