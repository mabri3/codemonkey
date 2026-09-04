#!/bin/bash
# Cycle 81 consolidated CLI sweep: every sub-command surface still answers
# at HEAD. Read-only / help probes only (no runs, no mutations).
cd /Users/bharris/Programs/CodeMonkey || exit 1
export HOME=/tmp/cm-reg-sweep
mkdir -p "$HOME"
run() {
  desc="$1"; shift
  out=$(uv run codemonkey "$@" 2>&1)
  code=$?
  first=$(printf '%s' "$out" | head -1 | cut -c1-90)
  echo "[$code] $desc :: $first"
}
run "help" --help
run "config" config
run "models" models
run "sessions" sessions
run "status" status
run "lessons-list" lessons list
run "digest-help" digest --help
run "jobs-list" jobs list
run "budget-help" budget --help
run "eval-help" eval --help
run "exec-help" exec --help
run "review-help" review --help
run "redact-help" redact --help
run "rules-compile-help" rules-compile --help
run "graph-help" graph --help
run "branch-help" branch --help
run "journal-list" journal list
