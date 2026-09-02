# Intent — CodeMonkey

## Problem
I want a coding-agent CLI (like `codex exec` / Claude Code / `agy`) that runs
against the local llama.cpp server (Qwen3.8-27B at
http://192.168.50.113:8080/v1) so it can be scripted by other agents
(Claude Code, ChatGPT/Codex) and CI pipelines to write code by request —
non-interactively, with machine-readable output.

## Proposed outcome
A `codemonkey` CLI (Python 3.11, uv, Typer, Rich, httpx) in this repo:
- Interactive REPL when run bare; `codemonkey exec "task"` non-interactive
  (stdout = final response, stderr = progress), JSONL event stream,
  structured output via JSON schema, resume, stdin piping.
- Copies `codex exec` semantics as closely as feasible (sandbox levels,
  approval policies, `--json`, `--output-last-message`, `--output-schema`,
  `resume`, `--skip-git-repo-check`, `-` stdin sentinel).
- Fully configurable via YAML (global `~/.codemonkey/config.yaml`, project
  `.codemonkey.yaml`) + `.env` for secrets; CLI flags override both.
- Multi-provider: OpenAI-style (`/v1/chat/completions`) AND Anthropic-style
  (`/v1/messages`) endpoints, selected per provider.
- Works with the local llama.cpp model, whose server rejects the OpenAI
  `tools` parameter (verified 500) — so tool calling must have a
  prompt-based JSON fallback; native tool calls used when the
  protocol/server supports them.
- Typical coding-agent tool set (union of codex/claude/agy): shell,
  read_file, write_file, edit_file, list_dir, search, glob, update_plan,
  web_fetch.
- Modular strategy architecture: compaction, memory, and session state must
  be pluggable strategy interfaces selected via config (each domain has >=2
  implementations), so different strategies can be tried later.
- After base cycles 1-9 (loop 1), run 2 more improvement loops (loops 2 and
  3) with the same autonomous process: each begins with a web-research cycle
  that picks the best "10x" improvements for a coding agent and appends
  build cycles. NO human approval between loops; the user reviews once after
  loop 3.

## Affected users/systems
- Me: local agent runs, CI on this Mac.
- Other agents calling `codemonkey exec` as a subprocess (Claude Code,
  Codex) — they need clean stdout + stable exit codes.
- The local llama.cpp server at 192.168.50.113:8080 (read-only for us;
  we only send chat requests).

## Constraints
- Python 3.11 via uv (system python is 3.9). Pin 3.11.
- No LLM SDK lock-in: raw httpx for both protocols (SSE parsing hand-rolled)
  so adding a provider = config, not code.
- Repo-local git identity (no global git identity on this machine).
- Must respect `build/STOP`, one commit per cycle.

## Open questions
- (resolved) command name: `codemonkey`, config dir `~/.codemonkey/`.
- (resolved) config: `~/.codemonkey/config.yaml` + `.codemonkey.yaml` +
  `.env`; env vars override YAML; CLI flags override all.
- (resolved) tools: native where supported, prompt-protocol fallback always
  available; `tool_protocol: auto|native|prompt` per provider.
- web_search tool: v1 ships `web_fetch` only (configurable); no search
  backend assumed.
