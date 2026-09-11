# Sweep classification — endpoint-gated vs model-gated (102F10)

Generated 2026-09-11T03:51:15Z by `build/sweep_endpoint_gated.py — each row run end-to-end through the released binary against build/stub_provider.py, replies conditional on request content`.

`build/acceptance_sweep.sh` reports one BLOCKED verdict for nine rows when no endpoint answers. That verdict conflates two different blockers, and only one of them is a reason to waive a row at v4.0.

## Counts

- rows classified: **9**
- endpoint-gated: **9**
- model-gated (whole row): **0**
- green with a run behind it: **9** — of which **5** carry no model clause at all and **4** keep a named residual
- red: **0**

## Rows

| row | class | verdict | what the green means |
|-----|-------|---------|----------------------|
| A4 | ENDPOINT-GATED | PASS | exit=0 listing='stub-model' |
| A5 | ENDPOINT-GATED | PASS | exit=0 out='pong' (rule fires only if the prompt reached the wire) |
| A6 | ENDPOINT-GATED | PASS | exit=0 json-lines=4 unparseable=0 types=['item.completed', 'thread.started', 'turn.completed', 'turn.started'] |
| A7 | ENDPOINT-GATED | PASS | exit=0 out='banana' (rule fires only if stdin reached the wire) |
| A9 | ENDPOINT-GATED | PASS | exit=0 stdout-has-sentinel=True stderr-has-command=True stderr-has-exit0=True |
| A10 | ENDPOINT-GATED | PASS | exit=0 payload={'project_name': 'codemonkey', 'programming_languages': ['Python']} (rule fires only if the schema reached the wire) |
| A11 | ENDPOINT-GATED | PASS | exit=0 thread=d7583635f6b3 out='zebra' (rule fires only if the HISTORY reached the wire) |
| A12 | ENDPOINT-GATED | PASS | exit=0 thread-in-listing=True |
| A16 | ENDPOINT-GATED | PASS | exit=0 chars=1110 (rule fires only if the DIFF content reached the wire) |

## v4.0 exception list (named, one per row)

A row is waived **for one clause**, never as a class. A blanket "endpoint down" waiver is not an exception list.

**A4** — spec.md A4 says "(live server call)": a listing served by the configured box's own /v1/models. Closed by: endpoint up, re-run A4 with no stub.

**A5** — a real model obeying a one-word instruction. The stub proves the prompt reached the endpoint and the reply was rendered; it cannot prove compliance. Closed by: endpoint up, live A5.

**A9** — spec.md A9 says "prompt protocol, live model": that a real 27B *chooses* the shell tool from a natural instruction. The stub proves the whole tool loop executes — parse, sandbox, subprocess, output, feed-back — end to end through the released binary; it cannot prove tool SELECTION. Closed by: endpoint up, live A9.

**A16** — spec.md A16 says "(live review run)": review prose written by a real model. The stub proves the diff was assembled into the prompt and ≥400 chars were rendered. Closed by: endpoint up, live A16.
