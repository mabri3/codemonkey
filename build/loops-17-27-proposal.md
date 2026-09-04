# Proposed forward loops 17–27 — research charters (NOT AUTHORIZED)

Date: 2026-09-03. Author: post-v1.0 roadmap pass requested by the user.
Baseline commit: `ca601e5`. Version: `1.0.0` (tagged). Suite: **460 passed**
in 57s. Closing sweep: **A1–A20 all exit 0 LIVE, zero BLOCKED**.

**Implementer note.** This arc is written to be executed by an agent that was
not present for loops 1–16 and has no conversation context. Everything it
needs is on this page or at a named path. Read §0 (handoff contract) first,
then §1 (verified current state), then §2 (the debt ledger — this is what the
arc is *for*), then §3 (binding arc rules), then the charter for the loop you
are opening. Do not skim §2; nine of the eleven charters exist because of a
specific row in it.

Same shape as `build/loops-5-10-proposal.md` and
`build/loops-11-16-proposal.md`: each loop opens with a research cycle
(`CYCLE R<N>`) that must do live web search with real citations, ≥5 candidates
and a ranked `SELECTED` section in `build/research-loop<N>.md`, and only then
appends `loop<N>:` build cycles to `build/plan.md` with literal verify probes.
**Nothing here selects a capability.** A charter names the question a loop must
research, the entry condition that makes the loop worth opening, and the exit
artifact. AGENTS.md §"How to create your plan" forbids silently expanding
scope, so the seeds below are candidates for the research cycle to confirm,
re-rank, or reject — never a pre-approved build list.

---

## §0 — Handoff contract (read before touching anything)

**The governing files, in reading order.** These are not background material;
they are the contract, and they win over anything you infer from the code:

1. `AGENTS.md` — the operating contract (cycle discipline, graphify duty,
   review-gate style, stop conditions). **This file wins over any instruction
   you receive elsewhere for anything inside this repo.**
2. `build/intent.md` — why the project exists; scope boundaries.
3. `build/spec.md` — binding acceptance criteria A1–A20 plus per-loop
   additions, with exact probes.
4. `build/plan.md` — the cycle ledger. **Checkbox state is ground truth.**
5. `SPRINT.md` — the HARD RULES (verify-before-mark, no fabrication, commit
   discipline). You inherit all of them.
6. `build/BUILD_REPORT.md` — per-loop acceptance records and honest gaps.
7. `BUILD_LOG.md` + `features.html` — append-per-cycle obligations.

**What a cycle is.** The only unit of work. A cycle = one scoped change +
its tests/probes + tests actually run + docs updated + one commit. There are
no "phases", no "tasks", no batched multi-cycle commits.

**Every cycle ends with, in this order:**

```
uv run pytest -q                      # must exit 0
# → dated entry appended to BUILD_LOG.md
# → features.html updated with the new surface
graphify . --update                   # graph must not go stale vs HEAD
git add -A && git commit -m "CYCLE <n> (loop<N>) — <what changed>"
```

**Verify before mark.** A `- [ ]` becomes `- [x]` in `build/plan.md` only
after you have run that cycle's literal verify probe and seen it pass. If a
probe cannot run (endpoint down, no key, no second provider), the ledger and
the report record **BLOCKED + the specific reason**. Fabricating or
paraphrasing a probe result is the one unrecoverable failure in this
framework — four loops of this repo's history are BLOCKED rows that were
recorded honestly and later cleared, and that is the expected behavior.

**Query the graph first.** `graphify-out/graph.json` exists. Any question
about structure, ownership, or call paths is
`graphify query "<question>"` / `graphify path "<A>" "<B>"` /
`graphify explain "<X>"` before ad-hoc file reading, and
`graphify . --update` at the end of every cycle. This is mandatory per
AGENTS.md, not a convenience.

**Stop and ask** when a charter is flagged `Core-design: YES` (or when a
`PARTIAL` charter's flagged sub-item is what you are about to build). Do not
hot-rework approved design — providers, protocol, strategy architecture,
sandbox semantics, session semantics. Ask the user, in one message, with the
specific decision and your recommendation.

**Hard stop conditions.** `build/STOP` exists; three consecutive failed probes
on one cycle (report, do not thrash); the user accepts or rejects at a gate.

**Environment.** Python 3.11.15 via `uv` only — never a global install, never
bare `python`/`pip`. Secrets live in `.env` and are referenced by `*_env`
names in config; they never enter git, probe output, or a report.

---

## §1 — Verified current state (checked against HEAD `ca601e5`, not recalled)

- **Version** `1.0.0`, tagged. `uv run codemonkey --version` → `codemonkey 1.0.0`.
- **Suite** 460 passed, 0 failed, 0 skipped, ~57s (`uv run pytest -q`).
- **Acceptance** A1–A20 all exit 0 against a live endpoint, zero BLOCKED rows
  (`bash build/acceptance_sweep.sh`; literal output in
  `build/acceptance_outputs/`).
- **Live provider** `local` → `192.168.50.176:8080` (authenticated), model
  `unsloth/Qwen3.8-27B-GGUF`. Override with `CODEMONKEY_BASE_URL`. This is a
  **single 27B-class local endpoint** — slow, and the only one reachable. That
  single fact is the entry-condition blocker for loop 22 and the cost driver
  behind loop 21.
- **Commands** (`uv run codemonkey --help`): `config`, `review`, `undo`,
  `eval`, `status`, `models`, `sessions`, `journal`, `jobs`, `lessons`,
  `redact`, `exec` (+ `exec resume`), plus the interactive REPL.
- **Tools** (13, `src/codemonkey/tools/`): `shell`, `read_file`, `write_file`,
  `edit_file`, `list_dir`, `glob`, `search`, `repo_map`, `web_fetch`,
  `update_plan`, `update_memory`, `delegate`, `delegate_batch`.
- **Machinery shipped across loops 1–16:** providers (OpenAI-style +
  Anthropic-style) with native and prompt tool protocols and a 500→prompt
  fallback; sandbox levels + approval gate + rule-based permissions; strategy
  registry (session-state jsonl/sqlite, compaction, memory); repo map with
  relevance ranking; context spill + slimming; execution journal with
  idempotent replay and forensics CLI; per-call checkpoints + `undo`; retry
  and availability failover; eval harness with golden suite, baselines, cost
  ledger, cache telemetry, strategy matrix, delegation matrix; durable jobs;
  lessons store with a verified-by-eval gate; `status` aggregator; secret
  redaction; `THREAT_MODEL.md`; committed `uv.lock`.
- **Graph** `graphify-out/` present and current at HEAD.

Read this section as *what exists*, not *what works well*. §2 is the
difference between the two.

---

## §2 — The debt ledger (why this arc exists)

Loops 11–15 each shipped a mechanism. Each of their charters said the
mechanism should be **kept only where measurement showed a win**, or should
deliver a **specific named probe**. In several cases the mechanism shipped and
the measurement or the probe did not. That is the pattern this arc has to
break — otherwise eleven more loops produce eleven more unvalidated
mechanisms, and the v2.0 record is worth no more than the v1.0 one.

| # | Debt | Evidence at HEAD | Charter that owns it |
|---|---|---|---|
| D1 | **Mid-turn crash resume never delivered.** Deferred in loop 7 with the journal named as its prerequisite; R12's own verify probe demanded "kill a run mid-turn, show the resumed run applying the interrupted mutation exactly once". Loop 12 shipped `jobs` + `exec --job` instead and closed. | `build/plan.md` loop12 cycles 43–44; `BUILD_REPORT.md` Loop 12 section | **Loop 19** |
| D2 | **Process-level containment never shipped.** R16 §1 researched macOS `sandbox-exec` / Linux bwrap; the `SELECTED` list dropped it. Only `tests/test_hardening.py` mentions it. The documented `shell` cwd-escape gap is still open under lexical containment alone — and `THREAT_MODEL.md` is the document that has to be honest about it. | `build/research-loop16.md` §1 vs `SELECTED`; `grep -rl "sandbox-exec\|bwrap" src/` → no hits | **Loop 20** |
| D3 | **Routing never measured.** R14's entry condition was ≥2 usable providers; only one was reachable, so loop 14 shipped availability *failover* only. Per-task-class routing — the actual R8 deferral, deferred again — remains unbuilt and unmeasured. | `BUILD_REPORT.md` Loop 14 (one criterion row); `src/codemonkey/exec.py` failover wrapper | **Loop 22** |
| D4 | **Delegation ROI unrecorded.** Loop 11 shipped roles, `review_rounds`, and `eval --delegation-matrix` → `matrix.json`. No report records a pass-rate / token / wall delta between arms. The charter's own words: roles "kept only where the harness shows a win at fixed cost". | `BUILD_REPORT.md` Loop 11 section; `src/codemonkey/matrix.py` | **Loop 21** |
| D5 | **Lessons ROI unrecorded.** Same shape: `lessons` + verified-by-eval gate shipped; no measured delta on the golden suite is recorded. R13 explicitly permitted a documented "no" as a valid exit and that exit was never evaluated. | `BUILD_REPORT.md` Loop 13 section | **Loop 21** |
| D6 | **Diff-gated approval + run timeline not shipped.** R15's narrow-scope fallback was "the diff-preview approval mode alone"; loop 15 shipped `status` and deferred live TUI + OTLP. No `diff` handling exists in `approvals.py` or `exec.py`. | `grep -n diff src/codemonkey/approvals.py src/codemonkey/exec.py` → no hits | **Loop 23** |
| D7 | **Anthropic native tool shape is unit-tested only.** The `input_schema` fix (51F1b) has never run against a live Anthropic endpoint; no key was available. A second protocol that has never spoken to its own server is a claim, not a capability. | `BUILD_REPORT.md` "Known gap" at close | **Loop 26** |
| D8 | **Two closing cycles are unchecked in the ledger.** `loop6-final` (`build/plan.md:595`) and `loop10-final` (`build/plan.md:951`) were never re-run. The ledger is ground truth, and it currently disagrees with the "loops complete" narrative. | `grep -n "^- \[ \] CYCLE" build/plan.md` → exactly these two | **Loop 17B** |
| D9 | **Shared job state is single-writer.** The multi-agent shared job store was deferred at loop 12 for want of file locking, while `delegate_batch` already runs workers concurrently. Concurrency exists; the state it would share does not tolerate it. | `BUILD_REPORT.md` Loop 12 notes; `src/codemonkey/jobs.py` | **Loop 24** |
| D10 | **Streaming partial responses are lost.** A mid-stream transport failure propagates and the partial tokens are discarded (documented at cycle 23, carried through R14 as a routing/retry concern, never closed). | `src/codemonkey/providers/openai.py:129` `_request_stream` | **Loop 22** |
| D11 | **Never run on a foreign repo.** Every task this agent has performed has been inside the repo that built it, on tasks written by the same process. No evidence exists about behavior on a codebase it did not author. | absence of evidence — no eval task, journal thread, or report outside this repo | **Loop 18** |
| D12 | **No retention policy under long jobs.** Journals, spills, checkpoints and session stores grow without bound; GC was an R12 seed that was never taken. A week-long job is exactly the case that has never been run. | `src/codemonkey/{journal,spill,checkpoints}.py`; R12 seeds | **Loop 25** |

Two prior decisions are **closed and must not be reopened** without a new
user instruction: the MCP client (rejected after five deferrals with
consistent recorded rationale), and concurrent model turns inside one thread
(the standing R8/R11 core-design flag — loop 24 may *ask*, not assume).

---

## §3 — Binding rules for this arc

These are in addition to `AGENTS.md` and `SPRINT.md`, and they exist because
of §2.

**R-A — Measure or delete.** A loop that adopts a mechanism must record raw
before/after numbers in `build/BUILD_REPORT.md` — pass rate, tokens, wall
clock, per arm, on named tasks. A loop that cannot produce separation must
either (a) record the mechanism as UNVALIDATED in the capability register with
the numbers that failed to separate, or (b) append a deletion cycle. "It
plausibly helps" is not an outcome. Three charters in this arc (18, 21, 22)
can legitimately close with a documented "no".

**R-B — No new surface until the debt above it is paid.** Each charter names
the §2 rows it discharges. A loop may not add capability outside its charter
to route around a hard entry condition; a blocked loop records BLOCKED and the
arc moves on.

**R-C — Every probe is literal and runnable.** A verify probe is a command
someone else can paste, plus the exact expected outcome (exit code, matched
string, numeric threshold). "Tests pass" is not a probe; `uv run pytest
tests/test_resume.py -q` → exit 0, ≥6 tests, is.

**R-D — stdout purity is inviolable.** `exec` text mode prints the final
answer and nothing else; `exec --json` prints JSONL and nothing else. Every
new surface writes to stderr or its own file. Any cycle in loops 23 and 25
carries a probe asserting this explicitly.

**R-E — The register is the release record.** Loop 17B produces
`build/CAPABILITY_REGISTER.md`; every loop after it updates the rows it
touches; loop 27 closes against it rather than against prose.

---

## The arc

| Loop | Theme | Pays | Entry condition | Exit artifact |
|---|---|---|---|---|
| 17B | Truth pass: claims vs evidence | D8, sets up D4/D5 | none — always openable | `build/CAPABILITY_REGISTER.md`: every feature marked PROVEN-LIVE / UNIT-ONLY / UNVALIDATED / DEAD |
| 18 | Foreign-repo dogfood | D11 | register exists | A friction log from real external tasks; the frictions become cycles and re-rank loops 23/25 |
| 19 | Mid-turn resume and crash truth | D1 | journal wired into production runs (done, 31F1) | A run killed mid-turn resumes and applies the interrupted mutation exactly once |
| 20 | Containment for real | D2 | register marks the sandbox row honestly | Process-level containment behind existing sandbox levels; `THREAT_MODEL.md` claims match enforcement |
| 21 | A harness that can say no | D4, D5 | register lists the UNVALIDATED set | Every unvalidated mechanism kept with numbers or deleted with numbers |
| 22 | Routing, actually measured | D3, D10 | **≥2 usable providers reachable at once** | Task-class routing adopted only on measured separation — or BLOCKED |
| 23 | The operator's eyes | D6 | loop 18's friction log | Diff-gated approval + a run timeline, stdout purity intact |
| 24 | Concurrency and shared state | D9 | loop 19 closed (crash semantics defined) | Concurrent workers share durable state safely, or the sharing is refused in writing |
| 25 | Long-thread economy | D12 | loops 19+24 closed; a multi-day job has run | Retention/GC/compaction policy proven on a job that outlives a run |
| 26 | Someone else's machine | D7 | loop 20 closed (containment is platform-specific) | Clean-machine install, Linux path, live Anthropic protocol verification |
| 27 | v2.0 closing acceptance | all | loops 17–26 closed; no open critic finding above LOW | Full re-sweep against the register, refreshed threat model, tag, Gate 3 handoff |

The ordering is a dependency chain, not a preference. Loop 21 cannot delete
anything until loop 17B says what is unproven. Loop 22's claims are
unfalsifiable without loop 21's harness. Loop 24 cannot define concurrent
crash behavior before loop 19 defines single-run crash behavior. Loop 25 has
nothing to garbage-collect until 19 and 24 produce week-long runs. Loop 26's
containment story is platform work that presumes loop 20 exists. Loop 27's
release claim is worthless if any of them left an open finding.

---

## CYCLE R17B — Loop 17B: truth pass, claims versus evidence

> **Relabelled 2026-09-03.** Loop 17 proper was opened and closed by a
> concurrent session while this arc was being written: its own `R17` selected
> an honest-completion gate (cycle 52) and static model routing (cycle 53),
> and `loop17-final` is committed. That work does **not** discharge this
> charter — no capability register was produced and D8 is untouched — so the
> truth pass keeps its position at the head of the arc under the label 17B.
> Everywhere these two arcs say "loop 17", they mean this cycle.
>
> Two notes for whoever runs it: cycle 52's claim-auditing gate is genuinely
> aligned with this charter and should be *credited* in the register, not
> re-derived. Cycle 53 shipped `model_routing` **and** `eval --route-stats`
> — the instrument that measures whether routing pays — and never ran it, so
> routing enters the register as UNVALIDATED and D3 stays open for loop 22.

**Question.** The v1.0 record says loops 1–16 are complete and A1–A20 are
green. §2 shows at least twelve places where a shipped mechanism, a charter
exit criterion, and the ledger disagree. For every capability this repo
claims, what is the strongest evidence that actually exists — a live probe, a
unit test, or nothing — and which claims must be demoted?

**Seeds.** A `build/CAPABILITY_REGISTER.md` with one row per shipped
capability: name, entry point (module + CLI surface), strongest evidence
(literal probe or test path), evidence class (PROVEN-LIVE / UNIT-ONLY /
UNVALIDATED / DEAD), and the §2 debt row it carries. Re-run of `loop6-final`
and `loop10-final` probes to resolve D8 — or, if their probes are obsolete,
an explicit superseded-by note rather than a silent tick. An audit of
`README.md` + `features.html` + `THREAT_MODEL.md` against the register, since
a doc that overclaims is a defect. A check that every `tests/test_*.py`
asserts behavior rather than existence. A dead-code / dead-flag pass: surface
shipped in loops 1–16 that nothing calls.

**Entry condition.** None. This loop is always openable and blocks the rest of
the arc.

**Core-design flag: NO.** This loop changes documents, tests and the ledger.
If it finds that a *behavior* is wrong, it files a fix cycle in critic style
(`build/critic-loop17.md`, `17F<n>` cycles) rather than rewriting design.

**Exit.** `build/research-loop17.md` (the audit method, with citations for the
audit technique used), `build/CAPABILITY_REGISTER.md`, `loop17:` cycles for
every demotion and doc correction, and D8 resolved in `build/plan.md`.

---

## CYCLE R18 — Loop 18: foreign-repo dogfood

**Question.** Every task this agent has run was written by the same process
that built it, inside the repo it built. Which of its capabilities survive
contact with a codebase it did not author — different language, different
layout, no `AGENTS.md`, no graph, unfamiliar test runner — and which frictions
are severe enough to be worth a cycle?

**Seeds.** A dogfood protocol: N real tasks (bug fix, feature, refactor, "why
does X happen") on ≥2 external repos of different shapes, run through `exec`
with the sandbox on, each producing a journal thread kept as evidence. A
friction log where every entry is a specific observed failure with the
transcript line that shows it — not an impression. `repo_map` relevance
quality on an unfamiliar tree. First-run experience: what does the tool need
that a stranger's repo does not provide? Whether the golden suite's tasks
resemble real ones at all (this bears directly on loop 21's harness). An
explicit anti-goal: do **not** fix frictions inside this loop — log them,
rank them, and let them become cycles here or re-scope loops 23/25.

**Entry condition.** `build/CAPABILITY_REGISTER.md` exists (loop 17B closed).
External repos must be ones the user is willing to have the agent operate in;
if none is available, R18 records BLOCKED with that reason and appends no
cycles — do not substitute a synthetic repo and call it foreign.

**Core-design flag: NO** for the log; **PARTIAL** if a friction's only fix
changes tool semantics — that fix ends by asking.

**Exit.** `build/research-loop18.md` + `build/friction-loop18.md` (ranked, each
entry with evidence) + `loop18:` cycles for the top frictions, each with a
probe that reproduces the friction before the fix and shows it gone after.

---

## CYCLE R19 — Loop 19: mid-turn resume and crash truth (D1)

**Question.** Loop 7 built the journal specifically so that mid-turn resume
would become possible, then deferred it. Loop 12 was chartered to deliver it
and shipped durable jobs instead. What does honest mid-turn resume actually
require — given a journal of intents, per-call checkpoints, and idempotent
replay already in the repo — and what is a resumed run allowed to assume?

**Seeds.** Replay of the in-flight intent exactly once (the exactly-once
property is the whole claim; at-least-once is a data-loss bug and at-most-once
is a silent-skip bug). Crash-point taxonomy: before the call, after the call
before the journal write, after the journal write before the effect, after the
effect. Reconciliation of journal state against the filesystem via the
existing checkpoints. What a resumed run must re-derive versus trust. Failure
of resume itself — a resume that cannot establish the crash point must refuse,
loudly, not guess. Interaction with `--job` write-back so a resumed run does
not double-advance a step.

**Entry condition.** The journal is wired into production runs (31F1, done).
The probe requires killing a live run, so a reachable endpoint is required; if
none is, R19 records BLOCKED rather than proving resume against a mock only.

**Core-design flag: YES** — "what a resumed run may assume" is session
semantics. R19 ENDS BY ASKING before any cycle changes what a session is.

**Exit.** `build/research-loop19.md` + `loop19:` cycles including, mandatorily,
a probe of this literal shape: start a run that performs a known mutation,
`kill -9` it mid-turn, resume it, and assert the mutation is present **exactly
once** (byte-compare or count assertion, not "looks right"), plus a probe for
each crash-point in the taxonomy.

---

## CYCLE R20 — Loop 20: containment for real (D2)

**Question.** R16 researched process-level containment and then dropped it
from the build list, leaving lexical containment as the only enforcement and
the `shell` cwd-escape gap open. What containment can this project actually
enforce on macOS and Linux behind its existing sandbox levels, and what must
`THREAT_MODEL.md` stop promising if the answer is "less than we implied"?

**Seeds.** macOS `sandbox-exec` profiles per sandbox level (noting it is
deprecated-but-present — the research cycle must establish current status with
citations, not assume). Linux bubblewrap / seccomp / user namespaces. The
honest fallback when no mechanism is available: fail closed, degrade loudly,
or refuse the level. Enforcement parity across levels (`read-only`,
`workspace-write`, and the bypass flag) so a level means the same thing on
both platforms or is documented as not doing so. An escape test suite that
attempts the documented cwd escape and asserts denial. Cost: containment that
doubles per-tool latency is a real regression and must be measured.

**Entry condition.** Loop 17B's register records the sandbox row honestly (a
containment loop that starts from an overclaimed baseline cannot tell whether
it improved anything).

**Core-design flag: YES** — process containment redefines what the sandbox
levels promise. R20 ENDS BY ASKING.

**Exit.** `build/research-loop20.md` + `loop20:` cycles, each with an escape
probe (attempt → assert denial + exit code + message) and a latency
before/after measurement; plus a `THREAT_MODEL.md` revision cycle whose probe
asserts every promise in the document maps to an enforcing test.

---

## CYCLE R21 — Loop 21: a harness that can say no (D4, D5)

**Question.** Loops 11 and 13 shipped delegation roles, review rounds and a
lessons system, each chartered to be kept only on a measured win, and no such
measurement is recorded. The blocker is real: the only endpoint is a slow
27B-class local server, so scoring two configurations is expensive. What makes
measurement cheap enough to be routine — and, once it is, do those mechanisms
survive it?

**Seeds.** Harness cost reduction: caching, parallel task execution against
the endpoint's real concurrency, smaller-but-still-discriminating task sets,
recorded-response replay for deterministic arms. Statistical honesty on small
N — how many golden tasks are needed before a pass-rate difference means
anything, and what to report when it does not (the arc's rule R-A depends on
this being answered). A standard arm-comparison report format written into
`build/BUILD_REPORT.md`. Then the actual scoring runs: delegation off vs
roles vs review_rounds; lessons injected vs not. Deletion cycles for whatever
does not separate, including removal of the CLI surface and tests, with the
numbers recorded in the register.

**Entry condition.** `build/CAPABILITY_REGISTER.md` lists the UNVALIDATED set
(loop 17B closed). A reachable endpoint is required; without one, R21 records
BLOCKED — this loop cannot be run on mocks by construction.

**Core-design flag: NO** for measurement; **PARTIAL** for deletion — removing
a shipped, documented capability is a user-visible change and the deletion
cycle ends by asking before it lands.

**Exit.** `build/research-loop21.md` + `loop21:` cycles, each carrying raw
per-arm numbers (pass rate, tokens, wall) in its verify probe, and a register
update flipping every UNVALIDATED row to PROVEN, DEAD, or an explicitly
recorded "measured, did not separate, kept because <reason>".

---

## CYCLE R22 — Loop 22: routing, actually measured (D3, D10)

**Question.** Model routing has now been deferred twice — R8 deferred it, R14
was blocked on having a single provider and shipped availability failover
instead. Do different task classes (compact/summarize, propose an edit,
review, decide) actually want different models, does routing beat a single
model at equal cost on the harness, and what does honest behavior look like
when a provider is reachable but wedged rather than down — the exact failure
this repo lost four loops to?

**Seeds.** Per-task-class routing declared in config and scored per class.
Health checks that distinguish unreachable / reachable-but-wedged / degraded,
since the failure mode that actually happened here was the middle one.
Declarative failover chains where every fallback is recorded in the journal
and never silent (the existing loop-14 wrapper is the starting point, not the
answer). Cost-aware routing against the existing cost ledger. **D10:** the
streaming partial-response gap — a mid-stream transport failure currently
discards partial tokens (`providers/openai.py::_request_stream`); decide
whether partials are retained, retried, or explicitly dropped, and make the
choice testable.

**Entry condition — hard.** **≥2 usable providers reachable at the same
time.** Routing cannot be measured on one endpoint; that is exactly how loop
14 ended. If a second provider is not available, R22 records BLOCKED with the
reason, appends **no routing cycles**, and may append only the D10 streaming
cycle, which needs one endpoint.

**Core-design flag: YES** — routing changes provider selection. R22 ENDS BY
ASKING.

**Exit.** `build/research-loop22.md` + `loop22:` cycles with raw before/after
tables **per task class**, or a BLOCKED record naming the missing second
provider, plus the streaming decision either way.

---

## CYCLE R23 — Loop 23: the operator's eyes (D6)

**Question.** R15's fallback position was that if nothing else shipped, the
diff-preview approval mode should. It did not; `status` shipped instead, and
approvals still gate on tool name rather than on the change itself. What is
the smallest surface that lets a human approve *what will actually happen* and
reconstruct *what did happen*, without violating stdout purity?

**Seeds.** Diff preview computed before a mutation is applied, and an approval
mode that gates on the diff rather than the tool name (a `write_file` that
rewrites a file is not the same risk as one that appends a line). A run
timeline over the existing JSONL event stream — what happened, in order, with
timing and cost. Unification of `journal` / `undo` / spill / checkpoint
browsing into one inspector rather than four commands. A REPL status line
(turn, tokens, cost, budget remaining). Structured run reports for CI. Loop
18's friction log **re-ranks these seeds** — if operators tripped over
something else entirely, that wins over this list.

**Entry condition.** Loop 18's friction log exists. If loop 18 was BLOCKED,
R23 narrows to the diff-gated approval mode alone, which is justified by D6
independent of any friction evidence.

**Core-design flag: PARTIAL** — a diff-gated approval mode changes approval
semantics and ends by asking; read-only viewers do not.

**Exit.** `build/research-loop23.md` + `loop23:` cycles, **each** carrying a
probe asserting stdout purity is unchanged (text mode = final answer only;
`--json` = JSONL only), per rule R-D.

---

## CYCLE R24 — Loop 24: concurrency and shared state (D9)

**Question.** `delegate_batch` already runs workers concurrently, while the
durable job store is single-writer and was deferred at loop 12 for want of
file locking. What must be true for concurrent workers to share durable state
safely — and is the honest answer that they should not?

**Seeds.** Locking for `jobs.py` (and any other store two processes can
touch): advisory locks, lock-free append designs, or single-writer with a
queue. Conflict semantics when two delegates advance the same step. Crash
behavior *under* concurrency, which is only definable once loop 19 has defined
it for one process — a lock held by a killed worker is loop 19's taxonomy plus
a new failure mode. Journal thread isolation so a dead delegate cannot poison
the parent (loop 11 claimed isolation; the register should say whether it is
proven). Observability of concurrent runs, feeding loop 23's timeline. The
standing R8/R11 flag — *concurrent model turns inside one thread* — may be
raised with the user here, but is not assumed.

**Entry condition.** Loop 19 closed (single-run crash semantics defined). If
loop 19 was BLOCKED, R24 narrows to locking with a documented, tested
single-writer guarantee and defers concurrent crash semantics explicitly.

**Core-design flag: YES** — shared mutable state across processes, and any
move on concurrent turns, are both core. R24 ENDS BY ASKING.

**Exit.** `build/research-loop24.md` + `loop24:` cycles including a probe that
runs concurrent writers against one store and asserts no lost update (exact
count assertion under N workers), or a written refusal with the reasoning that
produced it.

---

## CYCLE R25 — Loop 25: long-thread economy (D12)

**Question.** Journals, spills, checkpoints and session stores grow without
bound; GC was an R12 seed that was never taken, and no job in this repo's
history has outlived a single run by days. What does a week-long job actually
cost in disk, context and money, and what retention policy keeps it honest
without discarding the evidence the framework depends on?

**Seeds.** Measured growth rates per store under a long job (measure before
policy — this loop must not design a GC for a curve it has not seen).
Retention policy per store, with the explicit constraint that the journal is
the evidence base for resume (loop 19) and for the register, so "delete old
journals" has a correctness cost. Compaction policy for week-long threads:
what must survive a summary, tested by a probe that asserts a specific fact
survives N compactions. Cost accounting over a multi-day job against the
existing ledger. Resumable long-horizon eval tasks so the claim is testable at
all.

**Entry condition.** Loops 19 and 24 closed, and at least one job has actually
run across multiple sessions/days — if no long job exists, R25 records BLOCKED
rather than modeling a hypothetical one.

**Core-design flag: PARTIAL** — retention that deletes journal history changes
what the framework can later prove, and that specific decision ends by asking.

**Exit.** `build/research-loop25.md` + `loop25:` cycles, each with measured
before/after disk and context numbers, and a survival probe for compaction.

---

## CYCLE R26 — Loop 26: someone else's machine (D7)

**Question.** The project has been installed, run and accepted on exactly one
machine, against one endpoint, over one protocol path. The Anthropic protocol
has never spoken to an Anthropic server. What breaks on a clean machine, on
Linux, and on the second protocol — and what does a real distribution story
require?

**Seeds.** Clean-machine install from the committed lockfile, verified by a
probe that starts from nothing (container or fresh checkout + `uv sync
--locked`). Linux parity, especially for loop 20's containment, which is
platform-specific by construction. **D7:** live verification of the Anthropic
native tool shape (`input_schema`) against a real endpoint — this needs a key
and is BLOCKED without one, honestly, rather than declared fixed on unit
tests. Distribution: what a user installs, how it upgrades, how it rolls back.
Config portability: what breaks when `~/.codemonkey/` is empty and no
provider is reachable — the first-run experience for a stranger, which loop 18
will already have opinions about.

**Entry condition.** Loop 20 closed (there is a containment implementation
whose platform parity is worth testing). Each seed carries its own blocker:
no Linux host → the Linux rows record BLOCKED; no Anthropic key → D7 stays
open and is carried into loop 27's record as an open gap, not a pass.

**Core-design flag: NO** — packaging and platform work. A containment
difference between platforms that forces a semantic change is core and ends by
asking.

**Exit.** `build/research-loop26.md` + `loop26:` cycles with per-platform
probe results, and an explicit, honest table of what remains unverified.

---

## CYCLE R27 — Loop 27: v2.0 closing acceptance

**Question.** What does the closing record have to contain for a Gate 3
decision to be defensible in a way the v1.0 record was not — given that §2
exists precisely because the v1.0 record was accepted while twelve claims
outran their evidence?

**Seeds.** Full A1–A20 re-sweep plus every loop-2..26 criterion, live, with
zero BLOCKED rows or an explicit, individually justified exception list. The
capability register from loop 17B brought current, since rule R-E makes it the
release record — every row PROVEN-LIVE, UNIT-ONLY with a stated reason, or
DEAD. A closing critic pass in `build/critic-cycle6.md` style with no finding
above LOW left open. `THREAT_MODEL.md` refreshed against whatever loop 20
actually enforces. Final `build/BUILD_REPORT.md` covering loops 17–27 with the
git range. Version tag. Gate 3 handoff to the user with the specific decision
being asked for.

**Entry condition.** Loops 17–26 closed (shipped, or explicitly and
defensibly rejected/BLOCKED in writing) and no open critic finding above LOW
severity. A live endpoint must be reachable — a closing sweep with BLOCKED
live rows is exactly the failure this arc was written to avoid, and if the
endpoint is down, loop 27 waits rather than closing dishonestly.

**Core-design flag: NO** — it is an acceptance loop, and it changes nothing
but the record.

**Exit.** `build/research-loop27.md` (acceptance-record method, cited),
`loop27:` cycles ending in `loop27-final`: the closing record, the register at
final state, the tag, and the Gate 3 handoff.

---

## What this design deliberately does not do

- **It does not authorize anything.** `R17B`–`R27` are appended to
  `build/plan.md` unchecked and stay unchecked until the user says otherwise.
  Loops 6–10 held a blanket authorization; this arc does not inherit it.
- **It does not pre-rank capabilities.** Every seed above is a candidate for
  its research cycle to confirm, re-rank, or reject with fresh citations.
- **It does not assume its own loops succeed.** Loops 18, 21 and 22 can close
  with a documented "no", and 22, 25 and 26 have entry conditions this
  environment may simply not satisfy. A loop that cannot fail is not measuring
  anything.
- **It does not reopen closed decisions.** The MCP client stays rejected;
  concurrent model turns inside one thread stays a question for the user, not
  a plan.
- **It does not defer the core-design asks.** Five charters (19, 20, 22, 24
  and partially 21/23/25) end by asking the user rather than handing a
  selection to a build tick.
- **It does not add features to reach a number.** Nine of the eleven loops
  discharge a debt in §2. If §2 empties early, the correct move is to close
  the arc early and say so — not to invent loops to fill it.

---

## Successor arc

`build/loops-28-37-proposal.md` — the capability arc (loops 28-37): graph-
grounded retrieval, LSP grounding, certified/comparable measurement, fork-and-
branch execution, best-of-N with an execution verifier, generative and rubric
verifiers, corrections compiled into enforcement, adaptive memory, learned
context assembly, v3.0 acceptance. It opens only after `loop27-final`, and its
loops 31/32/35 carry hard entry conditions on loops 19, 20, 24 and 25 in this
arc — the debt paid here is what makes that arc buildable rather than
dangerous.
