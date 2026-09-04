# CAPABILITY_REGISTER — CodeMonkey v3.x (built cycle 81, loop 38)

One row per module in `src/codemonkey/` (56 rows = `ls src/codemonkey/*.py |
wc -l` at commit of this cycle). No UNVALIDATED rows: every module reads
PROVEN-LIVE (entry probe named), UNIT-ONLY (reason stated), or DEAD with its
deletion verdict. R-A disposal rule: a module that cannot earn an entry probe
is deleted in the cycle that audits it; the verdict is recorded, not silent.

Entry-probe legend (R-I grammar — a `codemonkey` sub-command's printed
output, or a real `run_exec`/`run_turns` run with an asserted observable
difference; `pytest` alone never qualifies):

- P-CLI — `codemonkey --help` + sub-command sweep, all exit 0
  (`build/probes/cycle81_cli_sweep.out`, 17/17 green at HEAD, incl. live
  `models` against home llama.cpp)
- P-EXEC — real exec runs (fake scripted provider or live home server)
- P-SWEEP — `bash build/acceptance_sweep.sh` A1–A20 (loop38-final re-runs it)
- P-<cmd> — the named sub-command's own probe transcript under build/probes/

## Active modules

| module | status | entry probe |
|---|---|---|
| __init__ | PROVEN-LIVE | `codemonkey --version` → version string, exit 0 (A1, P-SWEEP) |
| adaptivemem | PROVEN-LIVE | cycle-76 real-run A/B: adaptive injects only budget-selected lines (`build/probes/`, suite `test_memory_adaptive.py` R-I test) |
| affinity | PROVEN-LIVE | `route_key` per task in eval `results.json` (cycle77/78 transcripts carry it) |
| approvals | PROVEN-LIVE | cycle-8 exec probes: soft-deny notice on stderr, run continues; `--approval never` lifts |
| argvalidate | PROVEN-LIVE | cycle-57 probe: arg mismatch → `schema_mismatch` tool result in a real run |
| bestofn | PROVEN-LIVE | cycle-79 scripted 2-attempt real-exec run (first-pass wins, byte-identical reset) + `exec --best-of 2` → exit 2 (`build/probes/cycle79-cli.out`) |
| branches | PROVEN-LIVE | cycle-80 scratch-repo create/list/diff/remove (`build/probes/cycle80-cli.out`) |
| branches_cli | PROVEN-LIVE | same as branches (the `branch` command surface) |
| budget | PROVEN-LIVE | `codemonkey budget show --vram-gb 80` → kv bytes/token 262144, context_limit 90112 (this cycle, pure compute) |
| budget_cli | PROVEN-LIVE | same as budget (the `budget` command surface) |
| certify | PROVEN-LIVE | cycle-77 live trivial suite: `certificate: pass hoeffding-gate at_n=4` (`build/probes/cycle77-eval.out`). R-H: verdicts carry `kind: "hoeffding-gate"`; `sequential_verdict` deprecated alias. R-G triple — published: anytime-valid certificate (loop-30 claim); local: fixed-n Hoeffding bound replayed over prefixes; gap: replay inflates the error rate, so the old numbers are SUPERSEDED (re-labeled, not re-measured; the bound is unchanged) |
| checkpoints | PROVEN-LIVE | loop-2 live probe: destructive edit → `codemonkey undo` → byte-identical restore |
| claims | PROVEN-LIVE | this-cycle real-`run_exec` probe (`verify_claims=True`, fake provider asserting a false file claim): `[UNVERIFIED: ...]` marker in the final message + journal `verify_claims/flagged` record |
| cli | PROVEN-LIVE | P-CLI (every command parses and answers) |
| compile_rules | PROVEN-LIVE | `codemonkey rules-compile` (cycle-71 probe; `--help` green at HEAD, P-CLI) |
| config | PROVEN-LIVE | `codemonkey config` merged view, secrets masked (P-CLI; A2/A3/A19, P-SWEEP) |
| cost | PROVEN-LIVE | `--cost-summary` stderr ledger line (cycle-26 probe) |
| diffpreview | PROVEN-LIVE | `--approval preview` pre-apply unified diffs (R23B cycle probe) |
| digest | PROVEN-LIVE | `codemonkey digest` of a run thread (its cycle probe; `--help` green at HEAD, P-CLI) |
| digest_cli | PROVEN-LIVE | same as digest (the `digest` command surface) |
| dryrun | PROVEN-LIVE | `exec --dry-run` preview mode (cycle-59 probe) |
| eval | PROVEN-LIVE | live suites: trivial early-stop (77) + rubric suite (78) |
| events | PROVEN-LIVE | `from . import events` in exec; every `--json` run carries its `thread.started`/item stream (e.g. 79 event-sink traces) |
| exec | PROVEN-LIVE | `exec` text/JSON runs (A5–A7, P-SWEEP; 77/78 live suites) |
| graphquery | PROVEN-LIVE | cycle-74: `graph_*` agent tools in a real run + `codemonkey graph <symbol>` |
| grounding | PROVEN-LIVE | `pre_apply_validate` inside every write/edit tool call (exercised by the 79 scripted write runs) |
| instructions | PROVEN-LIVE | project-context block in real runs (cycle-18 probe; live evidence: the 78 rubric probe's model reasoning cites AGENTS.md precedence) |
| jobs | PROVEN-LIVE | `jobs list` (P-CLI) + `exec --job` step write-back (cycle-44 probe) |
| jobs_cli | PROVEN-LIVE | same as jobs (the `jobs` command surface) |
| journal | PROVEN-LIVE | journal threads written by real runs (31F1); `journal list` (P-CLI) |
| journal_cli | PROVEN-LIVE | same as journal (the `journal` command surface) |
| learnedctx | PROVEN-LIVE | cycle-75 real-run A/B: learned drops the non-overlapping fragment (observable system-prompt difference) |
| lessons | PROVEN-LIVE | `lessons list` (P-CLI) + injection path (its cycle probes) |
| lessons_cli | PROVEN-LIVE | same as lessons (the `lessons` command surface) |
| loop | PROVEN-LIVE | every exec run's turn loop (A9 tool loop end-to-end, P-SWEEP) |
| matrix | PROVEN-LIVE | `--strategy-matrix` bake-off run (its cycle probe) |
| native | UNIT-ONLY | OpenAI/Anthropic tool-call extraction unit-tested (A14, 13 provider tests); no live endpoint in service accepts the `tools` parameter (home llama.cpp 500s → prompt fallback, A9 mechanic), so the native path has no live proof — production runs take the prompt protocol |
| permissions | PROVEN-LIVE | rule hits enforced on journaled runs (R37F1 fix verification, suite 587) |
| protocol | PROVEN-LIVE | `TOOL_CALL:` prompt-protocol loop live on home server (A9; 77/78 suites run fully through it) |
| redact | PROVEN-LIVE | `codemonkey redact` secret-repair pass (its cycle probe; `--help` green at HEAD, P-CLI) |
| redact_cli | PROVEN-LIVE | same as redact (the `redact` command surface) |
| repl | PROVEN-LIVE | piped `fig` REPL probe (cycle-9) |
| repomap | PROVEN-LIVE | `repo_map: true` injection block (cycle-21 probe; assembly path intact at HEAD beside the cycle-75 strategy routing) |
| retry | UNIT-ONLY | backoff+jitter unit-tested; inducing live transport failures has no stable entry probe (cycle-23 numbers came from fault-injection harnesses, not a runnable command) |
| review | PROVEN-LIVE | `review --uncommitted` live (A16, P-SWEEP) |
| routing | PROVEN-LIVE | this-cycle real-`run_exec` probe (fake provider, `model_routing` prompt-glob rule): journal carries the `route` outcome record |
| rubrics | PROVEN-LIVE | cycle-78 live rubric suite: stdout-pass + rubric-fail → ok=false |
| rules_cli | PROVEN-LIVE | same as compile_rules (the `rules-compile` command surface) |
| sandbox | PROVEN-LIVE | read-only denies write+shell (A17; enforced in every exec run) |
| schema | PROVEN-LIVE | `--output-schema` validation + retry (A10 live, P-SWEEP) |
| sessions | PROVEN-LIVE | `codemonkey sessions` listing (P-CLI; A12, P-SWEEP) |
| slim | PROVEN-LIVE | called in the loop's result path (`loop.py`, every run with tool output) |
| spill | PROVEN-LIVE | stale-spill prune called unconditionally in the `run_exec` tail (every run) |
| status_mod | PROVEN-LIVE | `codemonkey status` (P-CLI, exit 0) |
| unload | UNIT-ONLY | single-slot unload fallback unit-tested (`test_unload_fallback.py`); live LM-Studio-evict induction is unavailable, so the fallback branch has no live proof |
| verifyhint | PROVEN-LIVE | verifier hint notice on runs without `verify_command` (cycle-63 probe) |

## Deletion verdicts (R-A, this cycle)

| module | verdict | evidence |
|---|---|---|
| lessons_gate | DELETED | `gate_lesson_with_eval` has zero src callers (`lessons_cli` manages verified flags directly via `mark_verified`); no entry probe earnable without a new surface. Removed with `tests/test_lessons_gate.py`. |
| rolepresets | DELETED | `resolve_role_preset` has zero src callers and no `role_presets` config key exists; no entry probe earnable. Removed with `tests/test_role_presets.py`. |
| truthpass | DELETED | no CLI command and zero src importers; the ledger-check function it served is superseded by this register. Removed with `tests/test_truthpass.py`. |

## Relocated (not a capability)

- `envquarantine.py` → `tests/envquarantine.py`: test-only support (used by
  `tests/conftest.py` quarantine fixture), no product entry point by design.
  Moved, not deleted; imports updated. Not counted in the 56.
