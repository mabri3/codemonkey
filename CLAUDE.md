# CLAUDE.md

Read and follow **AGENTS.md** in this repo root — it is the full operating
contract: required reading order, how to create your plan (cycles + literal
verify probes appended to `build/plan.md`), the HARD RULES inherited from
`SPRINT.md`, review-gate (critic) discipline, and stop conditions.

Quick orientation:
- Plan ledger: `build/plan.md` (checkbox state = ground truth)
- Acceptance criteria: `build/spec.md` (A1–A20 + loop additions)
- Acceptance state: `build/BUILD_REPORT.md` (`bash build/acceptance_sweep.sh` re-runs it)
- Per-cycle obligations: `BUILD_LOG.md` entry + `features.html` update + commit

Tests: `uv run pytest -q` · Docs guard: `uv run codemonkey --help` lists
exec/review/sessions/config/models (A18).
