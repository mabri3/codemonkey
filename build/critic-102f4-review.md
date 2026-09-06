# Critic report — CYCLE 102F4 audit: every control, real artifact or stand-in?

**Date:** 2026-09-05 · **Scope:** HEAD `2edbb9e`, suite **757/5** (green).
**Method (per charter):** break applied to the CODE in a detached worktree
(`/tmp/cm-102f4-wt`), target test file re-run, break reverted. A control
that stays green under its own break is defective. Where a control cannot
be exercised against the real artifact: BLOCKED with reason, never green.

**Method correction found during the audit:** the venv's editable install
points at MAIN `src`, so worktree breaks are invisible to in-process tests
(first E2 ran 10-passed on broken code and meant nothing). All break runs
below use `PYTHONPATH=<worktree>/src` with origin asserted
(`codemonkey.__file__` → worktree). E1 tripped via the binary path, which
runs worktree code regardless.

---

## Confirmed real (break → red; no finding)

- **E1 — 102F1 envelope_probe.** `events.stamp` deleted → conformance
  reports `2 failed` with `ConformanceFailure: event missing v:
  'thread.started'` (sibling's claim reproduced). Real-artifact. No finding.
- **E2 — 97F1 mixed-tree.** `shell_mutation` forced False → 2 failed
  (`test_mixed_tree_names_shell_path…`, `test_note_shell_lists_only…`),
  8 passed — the non-mutating control still passes. Real-artifact. No finding.
- **E3 — 96F1/C5 ordering.** `late_failures = failed` (ordering dropped) →
  `test_failure_before_first_landing_does_not_arm` fails, 8 passed.
  Input records are hand-built, but the shape is journal-native
  (`read_thread` output; the C96 re-baseline ran the classifier over all 56
  real threads) and failure-before-landing sequences are journal-producible.
  No finding.

## E5 — 98F1 loader controls (CONFIRMED real)

`_EDGE_KEYS` regressed to `("edges",)` → **5 failed, 2 passed**:
`test_compare_on_real_extract`, `test_cross_file_callers_are_observable`
(real `graphify` extracts — the fixture's top-level graph carries `links`),
`test_loader_reads_links_not_only_edges`,
`test_loader_ignores_backups_and_cache`, `test_path_endpoint…`.
The hand-built loader fixtures trip because their shapes match verified
real artifacts (top-level `links: 4612`, real `cache/ast` + dated dirs).
No finding. (An earlier E5 run reported "7 passed" — VOID: grep filtered
the break-script traceback; redone with visible break confirmation.)

## E7 — f2p wiring (CONFIRMED DEFECTIVE → FINDING F1)

Combined run, two breaks (`events.stamp` deleted + `_emit_repro` neutered):
**4 failed, 25 passed.**
- `test_conformance.py::test_offline_probes_green_on_binary`,
  `::test_envelope_probe_reads_a_real_stream_from_the_binary` — E1 names
  captured; the 102F1 fix trips on real breaks. No finding.
- `test_repro_gate.py::test_fix_run_counts_verified`,
  `::test_prefixed_run_is_unverified` — the emit break is REAL (loop-side
  controls detect it). This validates the experiment.
- `tests/test_f2p_gate.py` — **ALL GREEN with verdict emission deleted.**
  The matrix fake hand-appends `repro.verdict` dicts; nothing feeds a real
  loop trace into `label_task` or eval's f2p scoring. A shape drift between
  `repro.report()` and the labeler's expectations breaks measurement
  silently — the 102F1 defect class, sixth instance in the arc.

## Inspection triage (no break run; rationale stated)

- `test_sliding_window_no_llm_call` (poison provider): RIGHT shape — hostile
  dependency into the real artifact; trips if the code calls out. No finding.
- `test_anthropic_body_unchanged_by_cache_flag` (source grep): brittle but
  real-artifact; trips on the change it guards. No finding.
- `test_golden` regression pair: pure-function units on hand-built dicts;
  no test feeds real `run_suite` output into `check_regression`, and the
  docstring's "deliberately broken task → eval --check exit 1" path is
  live-gated (`requires_home`). OBSERVATION, unconfirmed — no F-cycle
  without a break run.
- `test_contract` gave_up pair + versioned-events: drive REAL `run_exec`
  with scripted providers; shape pinned from the 91F4 record. No finding.

## Self-referential verify probes (folded in, no separate cycle)

- C102's verify ("charter probe as written; tests green") — CONFIRMED by
  history as the shape that passed review without an operable break step.
- C103/C104 (unbuilt): same "charter probe as written" shape — when built,
  the probe must name the code break + rerun, not restate the charter.
- C97's "through `codemonkey exec`": the probe ran through `run_turns`,
  not the binary (no CLI-addressable scripted provider exists offline).
  Mechanism covered, path overclaimed — LOW.

## Findings (confirmed → own <cycle>F<n>; unconfirmed → observation only)

### F1 (HIGH) — f2p label/matrix never see a real loop trace
`tests/test_f2p_gate.py` fabricates `repro.verdict` dicts (hand `_v()` +
fake-exec appends); `_emit_repro` deleted leaves it fully green while
`test_repro_gate` goes red. Evidence path loop→verdict→label untested
end-to-end; shape drift breaks the quality gate's measurement silently.
**Verify probe (F1):** scripted `run_turns` with `verify_command` (fake
provider: write-test → fail → patch → pass), collect the REAL event trace,
feed it into `label_task` + eval f2p scoring → F2P; neutering `_emit_repro`
in a worktree MUST turn that test red.

### F2 (LOW) — C97 verify probe overclaims its path
Plan entry says "charter probe as written through `codemonkey exec`"; the
test drives `run_turns` in-process (no CLI-addressable scripted provider
exists offline, so the binary path is unexecutable here). Mechanism
covered, path overstated.
**Verify probe (F2):** entry reworded to the path taken, OR a
CLI-addressable scripted-provider probe added; either way the entry must
name a runnable path.

## Method rule (proposed, NOT adopted here — goes through the tool prompt
with the R-L items)

An in-process break run against a detached worktree is INVALID under an
editable install, because the venv resolves `import codemonkey` to MAIN
src: the break never takes effect and green means nothing. Evidence: first
E2 (10 passed on broken classifier), voided E5. Every break run in this
repo from here needs `PYTHONPATH=<worktree>/src` PLUS an asserted import
origin (`codemonkey.__file__`) before assertions run — the assertion is
load-bearing, not ceremony, and must not be dropped because a run
"obviously" picked up the worktree.
