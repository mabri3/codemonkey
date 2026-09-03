# Loop 10 Research — Interop, Distribution & Closing Acceptance (CYCLE R10)

Date: 2026-09-03 · Method: carried loop data + live docs-surface audit (real
`--help` output captured in probes) + web citations for the remaining open
question. Entry condition: critic-loop8's 7 HIGH/MED findings are FIXED and
verified (commits d0992a1, de1951d, e37bc25, e935627, 624d81d, b3b8c08,
c91808d — "7 critic fixes verified, suite 360/360"); no open finding above LOW.

## 1. MCP client — CLOSED PERMANENTLY (fifth and final deferral)

Four deferrals (loops 2-4 research) each recorded the same reason: dynamic
external toolsets dilute the prompt-protocol advertising and raise malformed-
call rates on a 27B-class local model; the fixed 13-tool surface is a
deliberate optimization. Nothing in loops 5-9 changed that calculus: the tool
registry is deliberately static, the prompt block is byte-stable BECAUSE the
tool set is static (cycle 22 prefix stability depends on it), and the new
delegate/delegate_batch tools already cover the org-extension use case via
subprocess isolation (own context, own journal thread) without protocol
churn. **Decision: closed — no MCP client. Revisit only if a deployment needs
live external systems AND runs a model large enough to tolerate dynamic tool
advertising.**

## 2. Config-declared tool extension point — SHIPPED (delegate IS the point)

Rather than arbitrary in-process tools (the MCP failure mode), the shipped
extension point is the `delegate` tool: any external capability reachable
from a shell can be composed by pointing a delegated run at it, with its own
sandbox, journal thread, and result cap. Documented in README (see docs
audit).

## 3. Packaging & versioned release — VERIFIED SHIPPED

pyproject.toml carries name/version/description/readme/requires-python/
dependencies (verified in probes/cycle40 docs audit). `uv run codemonkey
--version` → `codemonkey 0.1.0` (A1). Release readiness item: bump version to
**1.0.0-rc1** at loop10-final, tagged, with CHANGELOG.

## 4. Docs surface audit — DONE (audit results below, gaps fixed in cycle 39)

Commands shipped: exec (+resume), review, sessions, journal, undo, eval,
models, config — 8 subcommands + REPL no-subcommand entry.
exec flags audited: 19 flags incl. --json, --output-schema,
--output-last-message, --sandbox, --approval, --provider/--model, --cd,
--add-dir, --skip-git-repo-check, --ephemeral, --max-turns, --timeout,
--dangerously-bypass-approvals, --no-project-instructions, --cost-summary.
**Gap found: README predates loops 2-9 (no journal/undo/eval/delegate/
permissions/verify-gate documentation). Fix cycle 39 rewrites README +
features.html as the docs deliverable.**

## 5. Closing acceptance — loop10-final scope

Full A1-A20 re-sweep + every loop-2..9 criterion + final BUILD_REPORT with
git range and honest gaps. A9-class slow-hardware exceptions recorded per
precedent.

## SELECTED (loop 10 build list)

1. **CYCLE 39 — docs & packaging release prep**: README rewrite (all 13
   tools, 8 commands, permissions/delegate/verify/checkpoints), version
   1.0.0-rc1, CHANGELOG.md.
2. **CYCLE loop10-final — closing acceptance**: full sweep + all-loop criteria
   table + git range + gaps; Gate 2 handoff.
