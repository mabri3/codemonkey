# Loop 17 Research — Measured Trust: Model Routing + Completion Honesty (CYCLE R17)

Date: 2026-09-03 · Method: live web search (2 focused queries) + live evidence
from the Loop 17 entry probes (fizzbuzz test-file overclaim; A11's date
hallucination; .176 serving 3 distinct models).

**Note.** The 16-loop charter closed at v1.0.0 (Gate 2 pending user
acceptance). Loop 17 opens under the same operating contract at the user's
request ("build loop 17"). No loop-17 charter exists in
loops-11-16-proposal.md — this loop is scoped live from the two standing
defect classes observed in the first live week on .176.

## Live evidence (first week on .176)

1. **Fizzbuzz overclaim (2026-09-03 demo):** the model replied `FIZZBUZZ-OK`
   and produced `fizzbuzz.py` but silently skipped `test_fizzbuzz.py` despite
   the task saying "also create". A naively-trusting supervisor accepts the
   claim; only an independent check catches the lie.
2. **A11 date hallucination:** the resume probe answered with fabricated
   dates ("2026-07-10") for real memories — plausible-but-wrong metadata, the
   same *trust the narration, not the claim* class.
3. **.176 serves 3 models** (`unsloth/Qwen3.8-27B-GGUF`,
   `lmstudio-community/Qwen3.8-27B-GGUF`, `unsloth/Qwen3.6-35B-A3B-MTP-GGUF`)
   behind one authenticated endpoint — routing substrate exists but is unused.

## Researched capabilities

### 1. Honest-completion enforcement (outcome checks over reported success)
- Sources:
  - https://insights.reinventing.ai/articles/ai-agents-self-verification-production-2026-04-02 —
    production shift from "did the agent SAY it completed" to "does the result
    meet OBJECTIVE success criteria".
  - https://pub.towardsai.net/how-multi-agent-self-verification-actually-works... —
    LLMs self-agree without checking; independent verification needed.
  - https://arxiv.org/html/2602.03485v1 — self-verification tokens rarely
    change outcomes; external checks beat self-checks.
- Why: the fizzbuzz case is exactly this. A `verify_claims` mode that audits
  the reply's claims against observable state (files it said it wrote exist?
  commands it said passed produce real output?) converts narration into
  checked facts. **SELECTED (cycle 52).**

### 2. Per-task model routing rules (static rules, measured)
- Sources:
  - https://arxiv.org/html/2601.07206 — routing benchmark: routing decisions
    need task features, not vibes.
  - https://dasroot.net/posts/2026/03/multi-model-routing-llm-selection/ —
    per-task-type routing strategies.
- Why: .176 exposes 3 models behind one endpoint. A `model_routing` config —
  glob rules on the tool role (e.g. `review` → 35B MoE model, `exec` simple
  turns → default) — with the journal recording route decisions gives
  measurable per-route cost/quality from the eval harness. LLM-as-router and
  embeddings routers stay NOT SELECTED (a second LLM call per turn costs more
  than it saves; static rules are measurable and fail-closed). **SELECTED
  (cycle 53).**

### 3. LLM-judge routing (LLMRouterBench classifier approaches)
- Learned router trained on accuracy data — needs a corpus + training loop.
  **NOT SELECTED** (no training budget; revisit if route stats from 53 justify).

### 4. Multi-agent self-verification (verifier agent)
- Covered partially by loop-11 adversarial review. The honest-completion gate
  (cycle 52) is DELIBERATELY rule-based, not LLM-judged, per the self-agreement
  evidence above. A second `verifier` ROLE is already shipped (loop 11);
  nothing new required. **NOT SELECTED as separate build.**

## SELECTED (loop 17 build list)

1. **CYCLE 52 — honest-completion gate (`verify_claims`)**: post-turn audit
   mode (off by default) that checks the final reply's factual claims about
   actions against journal/exit-state evidence: "I created X" → X exists;
   "tests pass" → the test tool/command outcome in the journal is ok. Missing
   evidence demotes completion: reply rewritten with a `[UNVERIFIED]` marker
   appended + journaled as `unverified_claim`; exit code unchanged (the
   caller's problem, honestly flagged).
   verify: unit (≥7 tests: file-existence claim check, test-pass claim check,
   missing evidence → marker, journal record, off-by-default, evidence present
   → no marker, reply without claims → no-op).
2. **CYCLE 53 — static model routing**: `model_routing: [{when: {tool_role|
   prompt_glob}, provider/model}, ...]` first-match rules selecting
   provider+model per task; route decision journaled; `--route-stats` on eval
   printing per-route pass_rate/tokens from the matrix machinery.
   verify: unit (≥6 tests: first-match wins, fallback to default provider on
   no match, route recorded in journal, route-stats aggregation, invalid rule
   rejected, role-keyed routing).
3. **CYCLE loop17-final — acceptance**: sweep + report + push.
