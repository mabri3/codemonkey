#!/bin/bash
# Wrapper: run a command with the temporary unblock provider env wired up.
# Sources the key from opencode auth.json (never echoed anywhere).
# Usage: build/probes/with_unblock.sh <cmd...>
set -e
cd ~/Programs/CodeMonkey
export CODEMONKEY_UNBLOCK_KEY="$(python3 build/probes/unblock_key_env.py)"
export CODEMONKEY_PROVIDER=unblock
exec "$@"
