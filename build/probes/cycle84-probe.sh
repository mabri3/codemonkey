#!/usr/bin/env bash
# CYCLE 84 R-I probe — the skills strategy + tool surface through the CLI.
#   (a) config shows `skills: 'off'` effective by default (A19 surface)
#   (b) unknown strategy name -> exit 2 listing the valid names
#   (c) skill_runner is directly addressable: python -m ... TOOL_PY ARGS_JSON
set -u
cd "$(dirname "$0")/../.."
REPO=$(pwd)
T=$(mktemp -d)

echo "=== (a) codemonkey config (skills default) ==="
uv run codemonkey config | grep -A6 "^strategies:" | head -7
echo "exit=$?"

echo "=== (b) CODEMONKEY_STRATEGY_SKILLS=bogus ==="
CODEMONKEY_STRATEGY_SKILLS=bogus uv run codemonkey config > /dev/null 2> "$T/bogus.err"
echo "exit=$?"
cat "$T/bogus.err"

echo "=== (c) skill_runner direct ==="
cat > "$T/tool.py" <<'PY'
def run(args, ctx):
    return {"ok": True, "output": "runner-direct:" + str(args.get("n"))}
PY
(cd "$T" && uv run --project "$REPO" python -m codemonkey.skill_runner "$T/tool.py" '{"n": 7}')
echo "exit=$?"
rm -rf "$T"
