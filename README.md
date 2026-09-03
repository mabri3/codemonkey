# codemonkey

A scriptable, headless coding-agent CLI for **OpenAI-style and Anthropic-style
endpoints** — built to run unattended against a **local llama.cpp server**
(~27B-class model, ~32k context), but happy in front of any OpenAI-compatible
API.

Python 3.11 · uv · Typer · Rich · httpx · zero LLM SDKs (raw wire protocol).

## Install

```bash
git clone https://github.com/mabri3/codemonkey.git
cd codemonkey
uv sync
uv run codemonkey --version   # 1.0.0-rc1
```

Configure providers in `~/.codemonkey/config.yaml` (defaults: `local`
llama.cpp at 192.168.50.113:8080 + `anthropic`) or via `CODEMONKEY_*` env
vars. Secrets are referenced by env-var NAME (`api_key_env`), never stored.

## Commands (8 + interactive REPL)

| Command | Purpose |
|---|---|
| `exec PROMPT` | one-shot run; `--json` emits a JSONL event stream; `--output-schema` structured output |
| `exec resume THREAD` | continue a persisted session |
| `review [--uncommitted]` | unified diff → one read-only review turn → verdict |
| `sessions` | list persisted threads (rich metadata) |
| `journal list/tail/show` | execution-journal forensics (intents, outcomes, failure classes) |
| `undo [--list]` | restore files from pre-edit checkpoints |
| `eval SUITE.yaml` | golden-task harness; `--check` regression gate; `--strategy-matrix` compaction bake-off |
| `models` / `config` | provider listing / effective config (secrets masked) |

Running `codemonkey` with no subcommand starts the interactive REPL.

## The 13 tools

`shell` · `read_file` · `write_file` · `edit_file` (SREP search/replace blocks
+ batched multi-file atomic apply) · `list_dir` · `glob` · `search` ·
`update_plan` · `web_fetch` · `repo_map` (7-language symbol scan, relevance-
ranked, budget-capped injection) · `update_memory` · `delegate` /
`delegate_batch` (isolated child runs, depth-1) — governed by **rule-based
permissions** (`permissions.rules`: deny → ask → allow, first match wins) and
the approval policies (untrusted / on-request / never).

## Reliability features

- **Checkpoints/undo** — every mutating write snapshots first; per-workspace scoping
- **Verify gate** — `verify_command` runs after mutating turns; failures feed
  bounded corrective turns
- **Execution journal** — per-thread intent/outcome records with a failure-class
  taxonomy; args stored hashed, never raw; `journal` CLI for forensics
- **Idempotent mutating tools** — journal-keyed replay prevents double-apply on retry
- **Auto-compaction** — summarizing / sliding-window strategies, anti-decay
  invariants, bake-off measurable via `--strategy-matrix`
- **Prompt-prefix stability + cache_prompt** — measured 99% KV-cache hit on
  repeated prefixes
- **Streaming wall-clock guard** — a trickling stream can no longer hang a run
- **Observation budget + spill** — oversized outputs spill verbatim to disk
  with head/tail + pointer; deterministic slimming strips ANSI/whitespace noise
- **Retry/backoff** — Retry-After honored, full jitter, tools-500 falls back to
  prompt protocol immediately
- **Token/cost telemetry** — per-run summary (`--cost-summary`), cumulative ledger
- **Project instructions** — AGENTS.md/CLAUDE.md loaded nearest-first (32KB cap)

## Docs

- `features.html` — the living feature ledger (updated every cycle)
- `build/BUILD_REPORT.md` — per-loop acceptance reports (loops 1-10)
- `build/plan.md` — the full checkbox ledger (every cycle, every probe)
- `build/eval/` — golden suites, baselines, matrix results
- `AGENTS.md` — the operating contract for agents working IN this repo

## License

MIT
