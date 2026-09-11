# Loop 47 research — the evolving playbook + the consolidation verdict (CYCLE R47)

**Date:** 2026-09-11 · **Charter:** `build/loops-46-50-proposal.md` §B/§E ·
**Entry condition: FULFILLED** — loop 46 closed at `65db0a2` (six cycles,
868/5, KEPT-mechanism verdict with the R-K number named unmeasured); arc
authorized 2026-09-10 with the ordering waiver.
**Core-design: NO** — a new persistence surface + an R-A consolidation over
existing ones; neither touches providers, protocol, or sandbox semantics.
(One recorded note, not an ask: the consolidation DELETES `lessons.json` as a
store — an R-A disposal with precedent at cycle 81 and an explicit parity
gate, not silent removal.)

## Published context, UP FRONT (R-G)

- **ACE (Agentic Context Engineering, ICLR 2026,** https://arxiv.org/abs/2510.04618**)**:
  contexts as **evolving playbooks** curated by Generator → Reflector →
  Curator; **+10.6%** on agent benchmarks (AppWorld), **+8.6%** on finance
  (FiNER/Formula), **86.9%** average reduction in adaptation latency, learned
  from execution feedback **without labels**. Names the two failure modes
  this loop must design against: **brevity bias** (concise-summary optimizers
  drop domain insight they will never re-derive) and **context collapse**
  (monolithic rewrites erode detail — their case study: step 60 ≈ 18,282
  tokens at 66.7%; step 61 collapsed to 122 tokens at 57.1%, *below* the
  63.7% no-adaptation baseline). **Never a target for this repo's 27B-class
  endpoint** — the mechanism is the transferable part; the numbers are what
  larger models + different harnesses produced.
- **The consolidation case (Experience Compression Spectrum,**
  https://arxiv.org/html/2604.15877v1**)** — a citation analysis over 1,136
  references finds the memory community and the skill-discovery community
  cite each other **below 1%**, while both compress the same raw traces along
  one axis (traces → memory → skills → rules). This repo has five surfaces on
  that axis and no verdict; that IS the overlap this cycle resolves.
- **Dynamic Cheatsheet** (ACE's predecessor; test-time memory without weight
  updates) and **ExpeL** (https://arxiv.org/abs/2308.10144, AAAI-24:
  success/failure rules-of-thumb extracted by comparing trajectories) —
  the lineage the delta-curation design stands on.
- **Memory-for-agents survey** (https://arxiv.org/html/2603.07670): the
  bottleneck moves from storage to **relevance** once history outgrows the
  window; multi-signal scoring beats pure cosine — supports keeping this
  repo's deterministic assembly (no embedding store exists here; nothing in
  loop 47 adds one).
- **ExpGraph** (https://arxiv.org/pdf/2605.30712): frozen executor + external
  experience store + *learned retrieval*; this repo keeps the executor
  frozen (no weight changes, ever) and the retrieval DETERMINISTIC — the
  same posture at a smaller scale.

## In-repo grounding (graphify query + reads at `65db0a2`)

The five surfaces, as they actually exist:

| surface | what it stores | who writes | what gates it | wired? |
|---|---|---|---|---|
| `lessons.py` (`~/.codemonkey/lessons.json`, C45/loop13) | mined lessons (per-failure-class text) | subsystem from journal | `verified=False` drafts; **only eval runs may `mark_verified`**; `retrieve(verified_only=True)` | yes — plus `lessons_cli` |
| `compile_rules.py` (R34) | DRAFT `ask` permission rules from (tool, error_class) ≥ 2 | subsystem from journal classes | drafts stay drafts until the **operator** saves them into config | yes — `rules-compile` (print-only) |
| memory (`strategies/memory/{file,adaptivememory}.py`) | durable facts (`~/.codemonkey/memory.md`) | **operator + model** via `update_memory` | config strategy (`file`\|`adaptive`\|`none`) | yes — injected in project-context |
| `learnedctx.py` (R36) + `strategies/context.py` (`learned`, C75) | **nothing of its own** — it *ranks* fragments from four sources (memory, instructions, project-context, repo-map) | — (assembly) | `CODEMONKEY_CONTEXT_BUDGET`; pure + deterministic | yes |
| playbook | — | — | — | **does not exist** |

Two structural observations before the candidates: (1) `learnedctx` is not an
accumulation surface at all — it is the *selector*, and the verdict below
reframes it accordingly instead of inventing a sixth store; (2) the four
real stores have **three different trust postures** — operator-authored
(memory), subsystem-mined (lessons), operator-confirmed projection
(compile_rules) — and the playbook adds a fourth: **model-authored,
quarantined, delta-curated**. Merging across trust postures is what R-J
exists to prevent; the consolidation below merges by *role*, never by
*author*.

## Candidates (each: name, why, citations, attachment, R-I probe)

### C1 — Delta-curated playbook store (ACE's core, repo-sized)
Small candidate "delta" entries (bullets) merged into an existing playbook by
**deterministic, non-LLM logic**: append new by id, update counters in place,
exact-duplicate collapse. No big rewrite, so the collapse failure mode is
impossible BY CONSTRUCTION, not by prompt instruction.
**Attachment:** new `playbook.py` beside `skills.py` (same quarantine/provenance
idioms); store `.codemonkey/playbook/` gitignored by construction.
**R-I probe:** CLI round-trip (`playbook list|show`) + merge unit tests +
quarantined entries never load.

### C2 — Reflector as a deterministic journal pass
ACE's Reflector distills insights from successes/errors with an LLM; this repo
already has a deterministic classifier for the same signal (`failclass.py`,
`stuck`, `recovery`). The repo-sized reflector: a pure function mapping
journal records → **candidate deltas that cite their record indexes** —
no model call at reflection time (the model may then *use* deltas; it does
not get to authorize them).
**Attachment:** `playbook.reflect(journal.read_thread(t))`; evidence style
borrowed from `evidence.py` (claims cite indexes).
**R-I probe:** scripted failing run → `playbook reflect <thread>` prints
deltas naming the failure class + record indexes; the same run re-reflected
is byte-identical (determinism).

### C3 — Grow-and-refine maintenance (counters + dedup + boundedness)
ACE's maintenance loop: append new, update in place, prune semantic
near-duplicates eagerly or lazily. Semantic embeddings do not exist in this
repo (and loop 47 will not add one — see survey note above): dedup here is
**exact + normalized-text**, stated as the coarser guarantee it is.
**R-I probe:** the 50-round regression below.

### C4 — The 50-round collapse regression (from the case study)
Fifty rounds of synthetic deltas applied through the merge path must leave
**round-1 entries byte-stable** and keep total size linear-bounded — the
property a rewrite-style system fails. This is the loop's R-H-style
mechanism proof (no field rate; endpoint-free).
**Attachment:** test + a `playbook stats` line.
**R-I probe:** as described; early bytes compared byte-for-byte.

### C5 — Stability–plasticity measurement hook (for loop 50)
SWE-Bench-CL frames learning as stability–plasticity and scores it with
**CL-F1** (https://arxiv.org/pdf/2507.00014); loop 46 built the arms
(`skills-on/off`); loop 47 must expose the same arms for playbook-on/off so
loop 50 measures **both** surfaces with one harness. Deferred mechanics to
loop 50; this cycle only keeps the hook intact (no new measurement here).
**Attachment:** `skills_arms.py` generalizes to named surfaces; loop 50 does
the measuring.
**R-I probe:** n/a here — recorded as the loop-50 dependency.

### C6 — REJECTED: monolithic LLM rewrite of accumulated context
This is exactly the collapsed system in the ACE case study (18,282 → 122
tokens, below baseline). REJECTED for this arc on that evidence: the failure
mode is documented, severe, and the repo has no control that could catch a
slow collapse in a 27B endpoint nobody can currently probe.

### C7 — REJECTED (deferred): cross-agent / cross-repo playbook sharing
Same reasons as R46's C8: it converts a local, auditable surface into a
distribution channel, and R-J's provenance guarantee stops at this machine.
Revisit after loops 47 + 49 are PROVEN-LIVE.

## SELECTED (ranked)

1. **C1 + C3** — the playbook store with deterministic delta merge and
   grow-and-refine maintenance (the mechanism).
2. **C2** — the deterministic reflector (where deltas come from, evidence-cited).
3. **C5-adjacent injection** — `strategies.context` gains `playbook` so
   admitted entries actually reach a prompt (byte-regression guarded).
4. **C4** — the 50-round collapse regression (the mechanism proof).
5. **The consolidation** — executed as R-A below, in its own cycle.

## R-A CONSOLIDATION VERDICT — per surface (the required piece)

The five surfaces sit on one axis (raw trace → memory → skill → rule). The
verdict merges by ROLE and never across trust postures:

- **playbook — INTRODUCED (survives as THE agent-authored accumulation
  surface).** Quarantined by construction (R-J), delta-curated (never
  rewritten), injectable only when `admitted`, revocable via the store file
  itself. All future model-authored *prose that changes the prompt* lands
  here — not in lessons, not in memory.
- **lessons — DELETED INTO the playbook (storage), semantics preserved.**
  The verify-gate semantics (`verified=False` draft → eval marks verified →
  `retrieve(verified_only=True)`) carry over verbatim as the playbook's
  `kind: lesson` entry class; `lessons.json` becomes a migrated-then-removed
  artifact. Executed in the consolidation cycle with a **retrieval-parity
  gate**: every lesson retrievable before is retrievable after, or the
  deletion does not land. (`lessons.py`'s own citations — ACL 2026.acl-long.27
  experience-following; execute-distill-verify — are carried into the
  playbook module's docstring, not dropped with the file.)
- **memory — SURVIVES.** Different author (operator + explicit `update_memory`
  calls) and a different trust posture: memory is *stated*, not *mined*.
  Merging it into the playbook would blur provenance for no gain.
- **compile_rules — SURVIVES as the enforcement projection.** Its consumer is
  `permissions` (ask-rules), not the prompt; deleting it would remove the
  only path from recurring failure to a *gate*. It keeps sourcing the journal
  directly; the playbook may carry the same signal for prompt use, and
  neither replaces the other.
- **learnedctx — SURVIVES, REFRAMED: it is the selector, not a store.**
  Gains a fifth scored class (`playbook`, weight between memory and
  instructions — curated, small, but model-authored) and stays pure and
  deterministic. No new store, no embeddings.

Net effect: **one agent-authored store (playbook), one operator store
(memory), one enforcement projection (compile_rules), one selector
(learnedctx)** — the count of *accumulation surfaces* drops from "four
overlapping plus one empty" to two, with the deletion gated by parity.

## Cost note (R-F, charged against the loop that spends it)

Playbook merge is local compute (a JSON file, string ops); reflection is a
journal pass (no provider calls); the injection adds prompt tokens under
`CODEMONKEY_PLAYBOOK_BUDGET` — printed per run like every other budget.
The 50-round regression is offline.

## ACCEPTANCE (loop 47, core-design NO — terms, not an ask)

`uv run codemonkey playbook list|show` round-trips; a 50-round delta run
leaves early entries byte-stable and size bounded (transcript committed);
`context = playbook` changes the prompt by exactly the admitted entries
(byte-diff) and quarantined/evicted entries never appear; the consolidation
parity gate passes (every previously retrievable lesson retrievable) and the
deletion verdicts are in the register; suite green; report section
committed. The live R-K-style numbers (playbook-on/off arms) remain loop
50's job with the same BLOCKED discipline as loop 46.
