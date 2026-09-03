# Loop 11 Research — Delegation That Measurably Pays (CYCLE R11)

Date: 2026-09-03 · Method: live web search (2 focused queries) + the loop-9
substrate (delegate/delegate_batch/journal) + the loop-5 measurement rule
("no claim if the numbers do not separate").

## Researched capabilities

### 1. Role prompts for delegated runs (implementer / critic / verifier)
- Sources:
  - https://www.augmentcode.com/guides/coordinator-implementor-verifier —
    CIV pattern: decompose → parallel implement → independent verify.
  - https://arxiv.org/html/2606.20629 — cost-accuracy frontier of specialized
    agent roles (planner/executor/verifier); specialization pays when roles
    have distinct prompts and budgets.
  - https://arxiv.org/html/2510.07614v1 — traceability/accountability in
    role-specialized sequential agent systems.
- Why: `delegate(task)` exists but has no role semantics. Adding a `role`
  arg (implementer|critic|verifier) that selects a role prompt (system
  framing) turns the mechanism into the CIV pattern. The journal already
  records the delegated run.
- Cost: 1 cycle. **SELECTED.**

### 2. Adversarial review loop (inner loop, measurable disagreement)
- Sources:
  - https://arxiv.org/abs/2608.18167 — Adversarial Review: minimal agentic
    cooperation; the critic's structured disagreement drives bounded edit
    rounds; measurable quality delta.
  - https://asdlc.io/patterns/adversarial-code-review — critic enforces spec
    intent; bounded rounds prevent runaway.
- Why: a `review_rounds` arg on delegate (implementer → critic → bounded
  fix cycles) with the disagreement recorded. Bounded by max rounds; the
  verify gate (cycle 19) provides the objective stop signal when a
  verify_command exists.
- Cost: 1 cycle. **SELECTED.**

### 3. Delegation ROI measurement in the harness
- Sources: carried — loop-5 eval harness + loop-6 matrix pattern + cost
  telemetry are the measurement substrate; the R11 charter demands a
  measured answer, not vibes.
- Why: `eval --delegation-matrix` runs the golden suite with delegation on
  (roles) vs off, records pass_rate/tokens/wall per arm, reusing the cycle-28
  matrix pattern.
- Cost: 1 cycle. **SELECTED.**

### 4. Parallel fan-out of heterogeneous roles
- Sources: carried from loop-9 (delegate_batch); the CIV "parallel implement"
  step.
- Why: delegate_batch already parallelizes; roles compose over it
  (batch of [implementer, implementer, critic]).
- Cost: 0 (composition of 36-38 + role arg). Folded into cycle 40.

### 5. Coordinator role (plan decomposition)
- Sources: https://www.augmentcode.com/guides/coordinator-implementor-verifier —
  coordinator decomposes tasks into a dependency-ordered plan.
- Why: the parent run IS the coordinator (it decides what to delegate).
  A separate coordinator role duplicates the outer loop. **NOT SELECTED**
  (outer loop already coordinates; revisit if fan-out planning gets complex).

## SELECTED (loop 11 build list)

1. **CYCLE 40 — delegation roles**: `delegate(task, role=implementer|critic|
   verifier)`; role prompts frame the child's system context; role recorded in
   journal + result meta.
   verify: unit (≥5 tests: role accepted, role prompt differs in child argv/
   env, unknown role rejected, journal records role, default role =
   implementer).
2. **CYCLE 41 — adversarial review rounds**: `review_rounds=N` (default 0 =
   off): implementer → critic (structured FINDINGS/OK verdict) → bounded fix
   rounds; round results recorded.
   verify: unit (≥5 tests: rounds bounded, critic verdict parsed, fix rounds
   recorded in journal, OK verdict stops early, round count 0 = current
   behavior).
3. **CYCLE 42 — delegation ROI matrix**: `eval --delegation-matrix` runs the
   suite with delegation off vs on (implementer+critic roles), one arm per
   config, matrix.json shape as cycle 28.
   verify: unit (≥4 tests: two arms run, per-arm metrics, matrix.json shape,
   table renders).
