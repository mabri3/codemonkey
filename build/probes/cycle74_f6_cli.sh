#!/bin/bash
# 74F6 literal CLI probes (from build/plan.md verify text)
cd ~/Programs/CodeMonkey
echo "=== probe 1: graph nosuchsymbol_zzz (expect exit 1) ==="
uv run codemonkey graph nosuchsymbol_zzz
echo "exit: $?"
echo "=== probe 2: graph run_turns (expect exit 0, >=1 edge) ==="
uv run codemonkey graph run_turns
echo "exit: $?"
echo "=== probe 3: graph --help states exit codes ==="
uv run codemonkey graph --help
echo "exit: $?"
