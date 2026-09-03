# Loop 15 Research — Operator Surface & Observability (CYCLE R15)

Date: 2026-09-03 · Method: live web search (1 focused query) + the shipped
substrate audit (journal, jobs, spill, checkpoints, cost ledger, eval results
— all currently files/JSONL only).

## Researched capabilities

### 1. `codemonkey status` — one-shot run/operator summary
- Sources:
  - https://github.com/rothgar/awesome-tuis — dashboards read structured
    stores and render; the data layer already exists here.
- Why: every fact an operator needs exists (jobs, journal classes, latest
  eval baseline, cost ledger, sessions, spill size) but each needs its own
  command. One `status` command aggregates: job progress bars, journal
  failure-class totals, last eval baseline pass_rate, cost-ledger totals,
  pending spill bytes.
- Cost: 1 cycle. **SELECTED.**

### 2. Live TUI dashboard
- Sources:
  - https://github.com/rothgar/awesome-tuis — rich TUI ecosystem exists.
- Why: valuable, but heavy (Rich Live layouts, resize handling); the `status`
  command plus existing JSONL streams cover unattended supervision; a TUI is
  a UI luxury. **NOT SELECTED** (deferred; `watch`-style refresh can wrap
  `status` later).

### 3. OpenTelemetry-style export
- Sources: carried — otel-tui listed in awesome-tuis; standard OTLP export.
- Why: needs an OTLP endpoint/collector — infra a local CLI shouldn't
  require. **NOT SELECTED** (JSONL is already machine-parseable).

## SELECTED (loop 15 build list)

1. **CYCLE 48 — `codemonkey status`**: aggregates jobs (progress), journal
   class totals (last N threads), sessions count, latest eval baseline
   pass_rate, cost ledger totals, spill bytes; `--json` flag.
   verify: unit (≥6 tests: jobs progress, journal totals, sessions count,
   baseline read, cost totals, empty-store tolerance, json shape).
2. **CYCLE loop15-final — acceptance**: sweep + report.
