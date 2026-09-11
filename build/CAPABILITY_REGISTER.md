# CAPABILITY_REGISTER — CodeMonkey v4.x (built cycle 81, loop 38; live through the v4.0 close)

One row per module in `src/codemonkey/` (the count is re-checked against the
tree on every suite run — see the completeness note below). No UNVALIDATED
rows: every module reads
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
| lessons | PROVEN-LIVE | loop47 C111 (R-A): now a SHIM over the playbook store — `codemonkey lessons list` answers from the migrated playbook (verified/draft markers, tags `(shell, timeout)` preserved, ids `pb-…`); `codemonkey playbook migrate-lessons` → `migrated 3 lesson(s) … 2 verified admitted; parity OK` + old file ARCHIVED (`lessons.json.migrated-…`); retrieve returns the verified hit; a simulated drop turns the parity function red (`build/probes/cycle111-probe.out`); unit behavior re-pinned in `tests/test_lessons.py` (9) + `tests/test_lessons_migration.py` (6 incl. the planted-drop refusal + byte-identical rollback) |
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
| budgets | PROVEN-LIVE | conformance `budgetlimit` stub run through the RELEASED BINARY → exit 4 + `budget.exhausted` on the wire (loop44 C103) |
| changeplan | PROVEN-LIVE | `tests/test_changeplan_cli.py` drives the released binary: exit 3, tree byte-identical, `plan.rolled_back` naming the plan (102F6) |
| discover | UNIT-ONLY | repo-declared test-command discovery is asserted in-process (`tests/test_discover_verify.py`); no CLI surface of its own, and no run behind it |
| evidence | PROVEN-LIVE | `codemonkey evidence pack` → `verify`: fresh pack verifies, tampered pack exits 1, and verification is green with the model endpoint SWITCHED OFF (`build/evidence_probe.py`, loop45 C105/C106) |
| f2p | UNIT-ONLY | labels come from a real `run_turns` trace but only under pytest (`tests/test_f2p_gate.py`, 102F5); no CLI or eval surface has printed a label at HEAD |
| failclass | PROVEN-LIVE | `codemonkey journal show <thread>` prints taxonomy rows (C88 scripted failing exec run) |
| impact | PROVEN-LIVE | `codemonkey graph run_turns` prints cross-file `calls` edges; loader reads `links` (2328 nodes / 4339 edges, 892 cross-file) after 98F1 |
| ladder | UNIT-ONLY | scripted L1/L2/L3 runner green (`tests/test_segment.py`); the LIVE ladder is BLOCKED with the endpoint down (C99/C100) |
| partial | UNIT-ONLY | counts `write_file`/`edit_file` outcomes only — shell-mediated edits are not observable from the journal, and the limit is stated in its own output (96F1) |
| playbook | PROVEN-LIVE | `codemonkey playbook` full round-trip: no store → exit 0 honest empty; `merge` 2 deltas + 1 invalid kind → `added=2 updated=0 refused=1` with the reason printed (nothing partial); quarantined entries `load_admitted → []`; `show` prints counter+provenance; `admit` → loads; re-merge → counter 1→2 with the TEXT byte-identical; `revoke` → entry gone, `show` exit 2 (removed); journal carries `playbook.merged/admitted/revoked` (`build/probes/cycle107-probe.out`, loop47 C107); `reflect` = scripted failing run through real `run_turns` → CLI reflect prints evidence-cited pitfall deltas (same-group failures cite BOTH record indexes `[1,3]`; shell group taint-marked, write_file clean), byte-identical on re-run, no store side effect, then `merge` lands them `quarantined` with evidence on disk (`build/probes/cycle108-probe.out`, C108); `context = playbook` through real `run_exec`: quarantined/evicted never render (byte-equal to static), admitted render exactly the block on a `\n\n` boundary, budget enforced before spend (0 → byte-equal + "0/2 … block omitted"; partial → "1/2 … 1 held"; absent → "unlimited"), revoke → byte-equal again (`build/probes/cycle109-probe.out`, C109; break-verified gate `cycle109-break.out` — red under the break, byte-identical restore); 50-round collapse regression: round-1 entry byte-stable, 51 entries (no sprawl), recurring counter 55, monotone growth 6→78→153 words, CLI `stats`+`merge` green, and the REWRITE-style control LOSES its round-1 entry (`build/probes/cycle110-collapse.out`, C110; tests `test_playbook_collapse.py` incl. the control-failing predicate) |
| playbook_cli | PROVEN-LIVE | same as playbook (the `playbook` command surface) |
| recovery | PROVEN-LIVE | conformance `budget` stub run → `failure_report.budget_exhausted` on the wire from the released binary |
| repro | PROVEN-LIVE | conformance `verify` stub run → `repro.verdict` on the wire from the released binary |
| stuck | PROVEN-LIVE | conformance `gaveup` stub run → `stuck` on the wire from the released binary |
| skills | PROVEN-LIVE | `codemonkey skills list` on a repo with no store → exit 0 honest empty; a hand-written quarantined skill listed with status `quarantined`; `skills.load_admitted('.') == []` (quarantined NOT loaded) (`build/probes/cycle82-probe.sh`, loop46 C82); `codemonkey skills admit` → demo_ok ADMITTED exit 0 / demo_bad refused exit 1 (stderr in the journal) / re-admit eviction (`build/probes/cycle83-probe.out`, C83); `show|revoke|disable` → revocation byte-diffs + journal (`build/probes/cycle86-probe.out`, C86) |
| skills_cli | PROVEN-LIVE | same as skills (the `skills` command surface) |
| skill_runner | PROVEN-LIVE | directly addressable: `python -m codemonkey.skill_runner TOOL_PY ARGS_JSON` → one JSON result line (`build/probes/cycle84-probe.out`); exercised end-to-end by a real `run_turns` skill call (`tests/test_skills_strategy.py::test_admitted_skill_runs_through_the_loop_and_readonly_is_denied`) |
| skills_arms | PROVEN-LIVE | `codemonkey eval <suite> --arms skills-on,skills-off` → both arms + named statistic + transfer/retention + contamination, BLOCKED-with-reason when the endpoint is down, exit 0 (`build/probes/cycle87-arms-probe.out`); offline plumbing + both contamination branches pinned in `tests/test_skills_arms.py`; loop47 C112: covers BOTH learned surfaces (`--arms playbook-on,playbook-off` → both arms ran with the playbook accounting line, transfer/retention BLOCKED-with-reason `None`, contamination CLEAN, verdict BLOCKED; `build/probes/cycle112-arms-probe.out`); the contamination check now snapshots BOTH stores (skills + playbook) |
| taint | PROVEN-LIVE | coarse rule end-to-end in real `run_turns`: a web_fetch of the literal-payload fixture → `skill_create` refused, journal `skill.refused{reason:"tainted", source:"web_fetch"}`, store unchanged; the identical clean run writes (`build/probes/cycle85-probe.out`; `tests/test_skill_taint.py`, 7 tests incl. metadata-only and stickiness pins) |

**Completeness is now CHECKED, not asserted (C106, 2026-09-10).** The rows
above for loops 39-45 were added by an audit (`build/register_audit.py`) that
found **12 modules with no row at all** while this file claimed one row per
module: the claim was true when written (loop 38, cycle 81) and nothing ever
re-checked it — the same defect class as a binding document with no drift
control. `tests/test_register.py` now fails if a module in
`src/codemonkey/` has no ACTIVE row, or if an active row names a module that
no longer exists. Deleted modules belong in the deletion-verdict table below,
not in this one.

## R-G / R-F annotations — the modules the loops 38–45 arc added

The v4.0 acceptance terms (`build/loops-38-45-proposal.md` §R45; `CYCLE
loop45-final`) require every loop-38..44 row to carry its LOCAL / PUBLISHED /
GAP triple per R-G and its cost per R-F. The table below is that obligation,
**13 rows**. The set is DERIVED, not hand-picked: every top-level
`src/codemonkey/*.py` whose first commit descends from the R38 research
commit `2575515` (one `git log --diff-filter=A` pass;
`build/register_audit.py --triples` re-derives it, and
`tests/test_register.py` fails when a row here is missing, extra, or has an
empty cell — the release record is checked against the release, not against
a copy of itself). `stuck.py`'s first commit rides the concurrent GATE-2
commit `cf37b27` (cycle-89 work); the anomaly is recorded here so the
derivation is not a mystery. The clause says 38–44; the set runs through
loop 45's `evidence` because a boundary one module short of the arc's own
last generation is exactly how coverage claims drift.

| module (first add) | LOCAL | PUBLISHED | GAP | COST (R-F) |
|---|---|---|---|---|
| branches_cli (loop38 · C80) | scratch-repo CLI probe: create / list / diff / remove + exit-2 contract (loop38 report) | none — no published counterpart for the CLI surface (worktree isolation itself is standard git) | not applicable — mechanism row; no field rate claimed | local git ops only; no provider calls, no tokens |
| failclass (loop39 · C88) | `journal show` taxonomy rows on a scripted failing run (register probe) | AgentRx nine-category framing; step repetition 17.14% of 1600+ traces (research-loop39) | 4 classes mapped by rule; the rest honestly unmapped — forced labels refused | journal post-processing; zero provider calls |
| stuck (loop39 · C89) | conformance `gaveup` stub run → `stuck` event on the wire (released binary) | ignored-result moves 6.2% vs repaired baselines 1.2–4.9% (research-loop39) | deterministic (tool, class)×3 trigger; no local rate claimed | per-turn counter; nudges add ≤1 system message; no extra calls |
| recovery (loop39 · C90) | conformance `budget` stub run → `failure_report.budget_exhausted` on the wire | 82% of failed trajectories burn remaining budget after lock-in (research-loop39) | would-have-saved figures are emitted per run; no aggregate exists (no endpoint population) | consult + counters per turn; zero extra calls |
| repro (loop40 · C93) | conformance `verify` stub run → `repro.verdict` on the wire | generated-test reproduction literature (research-loop40) | F2P transitions measured in scripted runs only; live rate unmeasured | one run of the declared test command per gate event; no provider calls |
| discover (loop40 · C94) | declared-repo auto-verify on the trace (in-process; the active row is UNIT-ONLY) | none — no headline number for test-command discovery; offline hit rate 18/18 | false-gate rate unmeasurable (endpoint down) → no flip; revisit condition recorded | startup file checks; no tokens |
| f2p (loop40 · C95) | labels proven on a real `run_turns` trace (102F5); live arms BLOCKED with date | 63.0% F2P on TDD-Bench Verified, e-Otter++ (frontier reference, never a target) | **UNSTATED** — local rate unmeasurable without an endpoint | per-arm tokens/wall in `render_f2p_table`; live costs pending |
| partial (loop41 · C96) | classifier + scope-in-output; baseline 56 threads, 0 multi-edit attempts, rate **None** | none — no agreed metric for partial application (research-loop41) | no published number to stand next to; local denominator is zero (None, never 0.0) | counter is free; the atomic-plan path adds 0.2s + 20MB + one verify |
| changeplan (loop41 · C97) | induced mid-plan failure → byte-identical tree; `plan.rolled_back` on the wire (102F6) | none — atomic plan + rollback is a mechanism; no published counterpart | no field rate claimed (insurance row); shell-mediated paths named as outside the guarantee | opt-in `--atomic-plan`; 0.2s + 20MB + a second verify per plan |
| impact (loop41 · C98/98F1) | live extract after 98F1: 2328 nodes / 4339 edges, 892 cross-file `calls`; graph-vs-search counts reported both ways | architecture-aware repo-level generation; ARISE localization+repair (research-loop41) | graph-only vs search-only counts both reported; no accuracy claim | local graph read per query; no tokens |
| ladder (loop42 · C99/C100) | scripted L1–L3 runner green; LIVE ladder BLOCKED with date | BFCL ladder — frontier well above 27B-class (research-loop42) | **UNSTATED** — no local ladder numbers; the harness runs the moment a model answers | per-arm tokens/wall in eval renderers; live costs pending |
| budgets (loop44 · C103) | conformance `budgetlimit` run → exit 4 + `budget.exhausted`; the boundary proven by provider-call count | none — no published counterpart for runtime-enforced budgets (loop44 report) | defaults uncalibrated against real runs — stated as unmeasured | zero provider calls added; counter + one job-file write per breach |
| evidence (loop45 · C105/C106) | fresh pack verifies endpoint-off; tampered pack exits 1 (`build/evidence_probe.py`) | standards-track direction — tamper-evident trails / cryptographic tool-use binding (research-loop45); repo-scale version only | tamper-evident against casual editing, not a determined adversary — stated in THREAT_MODEL.md | local hashing; O(records); zero provider calls |

## Deletion verdicts (R-A, this cycle)

| module | verdict | evidence |
|---|---|---|
| `~/.codemonkey/lessons.json` (the STORE; the `lessons` module remains a shim) | DELETED INTO THE PLAYBOOK (loop47 C111) | R-A per `build/research-loop47.md`: one agent-authored accumulation surface, not two. Parity-gated migration: every previously-verified lesson retrievable after (two-way; drafts too), verified→`admitted`, tags→section encoding, retrieval scoring unchanged; old file ARCHIVED (`.migrated-<stamp>`), never destroyed; planted-drop tests refuse + roll back byte-identically (`build/probes/cycle111-probe.out`) |
| lessons_gate | DELETED | `gate_lesson_with_eval` has zero src callers (`lessons_cli` manages verified flags directly via `mark_verified`); no entry probe earnable without a new surface. Removed with `tests/test_lessons_gate.py`. |
| rolepresets | DELETED | `resolve_role_preset` has zero src callers and no `role_presets` config key exists; no entry probe earnable. Removed with `tests/test_role_presets.py`. |
| truthpass | DELETED | no CLI command and zero src importers; the ledger-check function it served is superseded by this register. Removed with `tests/test_truthpass.py`. |

## Relocated (not a capability)

- `envquarantine.py` → `tests/envquarantine.py`: test-only support (used by
  `tests/conftest.py` quarantine fixture), no product entry point by design.
  Moved, not deleted; imports updated. Not counted in the 56.
