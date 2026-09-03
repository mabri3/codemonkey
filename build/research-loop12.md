# Loop 12 Research — Long-Horizon Work Across Runs (CYCLE R12)

Date: 2026-09-03 · Method: live web search (2 focused queries) + the carried
substrate (sessions, journal, eval, plan ledger).

## Researched capabilities

### 1. Durable task files (workflow state ≠ session state)
- Sources:
  - https://www.mindstudio.ai/blog/workflow-state-vs-session-state-ai-agents —
    workflow state tracks task progress across steps/agents/sessions in a
    structured EXTERNAL store; session state is conversation.
  - https://fast.io/resources/ai-agent-workflow-state-persistence/ —
    workflow state survives restarts/crashes; resume days later.
  - https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk —
    explicit state schema beats relying on conversation history.
- Why: everything dies with the run today. A durable **job file**
  (`~/.codemonkey/jobs/<id>.json`: id, goal, steps [{id, status: pending|
  done|failed, note}], created, updated) gives update_plan a durable home and
  gives later runs something to pick up. `jobs` CLI + `job_resume` in exec.
- Cost: 1 cycle. **SELECTED.**

### 2. Crash-safe step transitions
- Sources:
  - https://tianpan.co/blog/2026-03-07-async-agent-workflows-long-running-task-design —
    checkpoint after each significant step; state = what you need to resume
    without redoing.
  - https://learn.microsoft.com/en-us/azure/durable-task/sdks/durable-task-for-ai-agents —
    durable execution for tool-calling agents.
- Why: step status changes must be atomic writes (tmp+rename) so a crash
  between "mark done" and "start next" never corrupts the job.
- Cost: folded into cycle 43 (atomic write helper). **SELECTED (folded).**

### 3. Job-aware exec injection (`--job <id>`)
- Sources:
  - https://airbyte.com/blog/agent-state-machines-for-business-workflows —
    model the workflow as an explicit state machine the agent reads/updates.
- Why: `exec --job <id>` injects the job's goal + step statuses into the
  project-context block and exposes `update_plan`-style step transitions the
  model can write back (via a `job_update` tool or structured marker).
- Cost: 1 cycle. **SELECTED.**

### 4. Multi-agent shared job store
- Sources: https://airbyte.com/blog/agent-state-machines-for-business-workflows —
  multiple agents on one state machine.
- Why: with delegate/delegate_batch, a shared job file lets a fan-out divide
  steps. But concurrent writes need locking. **NOT SELECTED this loop** —
  single-writer per job now; file-locking is the R13+ follow-up if fan-out
  jobs become real.

## SELECTED (loop 12 build list)

1. **CYCLE 43 — durable jobs module + CLI**: `jobs.py` (atomic JSON read/
   write, create/status/next-step helpers), `codemonkey jobs list|create|
   show|done|fail` CLI; crash-safe tmp+rename transitions.
   verify: unit (≥6 tests: create/show, step transitions, atomicity under
   simulated crash, list, done/fail, unknown job error).
2. **CYCLE 44 — `exec --job`: job-aware injection + step write-back**: the
   job's goal/steps inject into the project-context block; the model updates
   steps via a structured TOOL_CALL-free `JOB_STEP` marker parsed post-turn;
   statuses persist across runs.
   verify: unit (≥6 tests: injection contains goal+steps, marker parse,
   transition persist, cross-run resume shows progress, invalid marker
   ignored, ephemeral runs don't write); suite green.
3. **CYCLE loop12-final — acceptance**: sweep + report.
