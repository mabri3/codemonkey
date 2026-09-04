# Loop 40 research: the test loop as the primary control signal (CYCLE R40)

**Date:** 2026-09-04 · **Charter:** `build/loops-38-45-proposal.md` (R40) ·
**Entry condition FULFILLED:** R38 closed (loop38-final, 97404c3).
**Core-design PARTIAL:** default-on verification changes what "finished"
means — **R40 ENDS BY ASKING** (the default flip in C94 goes no further
than default-OFF machinery until the user approves it).

**Question** (charter): reproduction-test-first execution, the verify gate
promoted to default-on where a test command is discoverable, and
generated-test quality as a first-class risk (a test that never failed
proves nothing).

**Published number, UP FRONT (R-G):** ~63% fail-to-pass is a
FRONTIER-harness number — e-Otter++ reports 63.0% F2P on TDD-Bench Verified
(52.5% on SWT-bench Lite) via execution-feedback selection
(https://arxiv.org/html/2508.06365v3); EvoOtter reaches 75.3% with
Claude-Opus-4.7 (https://arxiv.org/pdf/2607.02854). This repo (single local
27B, no inference scaling, no test-selection machinery) will NOT match it;
loop-40 probes report the local F2P rate NEXT TO 63%, never as a chase.

## In-repo evidence

- Verify gate exists (loop 4: `verify_command`, `max_verify_retries`) but is
  opt-in per run; `--best-of` (cycle 79) made verification mandatory for
  multi-attempt runs only. Single runs still "finish" on model self-report.
- Eval harness scores stdout/exit/trajectory/rubric — never test outcomes.
  No capability writes or runs tests except via the model's own shell calls.
- `compile_rules` mines failures; nothing requires a reproduction before a
  patch. The loop-32 best-of work scored candidates with a machine check —
  loop 40 promotes the same idea to the DEFAULT path.

## Candidates

### C1 — Reproduction-test-first execution (Prove-It pattern)
For bug-fix runs: write the failing test BEFORE the patch (fail observed),
then patch, then pass observed. The agent-skills Prove-It pattern states it
plainly (https://github.com/addyosmani/agent-skills/blob/main/skills/test-driven-development/SKILL.md);
SWE-Doctor shows BRTs turn reports into executable feedback, with the caveat
that single-facet F2P tests induce partial patches — generate multi-facet
repros (https://arxiv.org/pdf/2607.00990v1). Mechanism here: a `repro.py`
gate module (write-test → run-expect-fail → allow-patch → run-expect-pass),
not a prompt suggestion.
*Why high-leverage:* makes "the bug is fixed" mean something observable
twice (fail, then pass) instead of once (model says so).

### C2 — Verify gate default-on where a test command is discoverable
If the repo declares how it tests itself (`pytest.ini`/`tox.ini`/`setup.cfg`
pytest section, `pyproject` pytest config, `package.json` test script,
Makefile `test` target), the run auto-sets its verifier to that command;
otherwise behavior is unchanged (no command invented, no failure). Cost
accounting per R-F: the auto-verify's wall/tokens print in the run summary.
*Why high-leverage:* verification becomes the default path without a single
config edit by the operator; undiscoverable repos are untouched (no false
mandates).

### C3 — Generated-test quality gate (F2P demonstration required)
"A test that never failed proves nothing": a generated test counts as
fix-evidence ONLY if it was observed failing pre-patch and passing
post-patch. Beyond-Fail-to-Pass sharpens this: F2P alone is insufficient —
only Rigorous tests (rule out plausible-but-wrong fixes, +8.5 Resolved)
help; Lax tests add nothing; cogenerated test+fix errors correlate 1.87×
(https://arxiv.org/abs/2607.19843). Mechanism: the quality gate records each
generated test's fail→pass transition in the verify report; tests that only
ever passed are labeled UNPROVEN, never counted. Full mutation testing is
explicitly OUT (cost); the fail-then-pass observation is the cheap,
honest subset.
*Why high-leverage:* directly disarms the "tests pass beautifully, refactors
look clean, behavior unverified" failure mode of AI-written tests.

### C4 — AssertFlip-style inversion (rejected)
Generate a PASSING test of current behavior first (LLMs are better at it),
then invert to a bug-revealing test (https://arxiv.org/abs/2507.17542).
Elegant, but it is a *generation tactic* for the model, not a control
signal for the harness — loop 40 is about what the harness requires, not
how the model writes. Rejected with reason; revisit if C1's direct
fail-first generation underperforms.

### C5 — Execution-budget for testing (rejected as a standalone)
Cost-effectiveness of code execution in agents
(https://arxiv.org/html/2606.26978v1): testing costs tokens/wall. Real
concern, but it is ALREADY covered by R-F accounting in every loop-40 probe
(cost/wall printed per probe) — no separate mechanism needed. Rejected as
redundant.

## SELECTED (ranked)

1. **C1 repro-first gate** → C93: `repro.py` (expect-fail → allow → expect-
   pass state machine around the test command) + loop wiring for fix runs.
2. **C2 discoverable default-on** → C94: repo-declared test-command
   discovery + auto-verify; BUILT default-OFF, flip AWAITING-ASK (changes
   what "finished" means).
3. **C3 F2P quality gate** → C95: fail→pass transition recorded per
   generated test; UNPROVEN label; golden-suite ON-vs-OFF measurement with
   local F2P next to published 63% (R-G), cost/wall (R-F), gate verdict
   (R-H).

**Rejected with reasons:** C4 (model tactic, not harness control), C5
(already covered by R-F probe accounting), full mutation testing (cost —
stated, not built).

## Cost note (R-F)

Research only (this file + searches). Build probes print turns, tokens,
wall, and the gate verdict for ON vs OFF arms.

## Appended cycles

`loop40:` C93–C95 + `loop40-final`, appended unchecked to `build/plan.md`,
continuing at 93. C94's default flip is AWAITING-ASK alongside R39's C91/C92
— one ask round covers both (termination policy + default-on verification).
