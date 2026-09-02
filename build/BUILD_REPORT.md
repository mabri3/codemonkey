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
