#!/usr/bin/env bash
# CYCLE 82 R-I probe — the skill store, through the RELEASED BINARY.
#   (a) no store      -> `skills list` exit 0, honest empty
#   (b) hand-written quarantined skill -> listed with status `quarantined`
#   (c) same store    -> skills.load_admitted('.') == []  (quarantined NOT loaded)
#   (d) skills --help -> the verb surface answers
set -u
cd "$(dirname "$0")/../.."
REPO=$(pwd)
T=$(mktemp -d)
mkdir -p "$T/home"

echo "=== (a) repo with no store ==="
(cd "$T" && HOME="$T/home" uv run --project "$REPO" codemonkey skills list)
echo "exit=$?"

echo "=== (b) hand-written quarantined skill ==="
mkdir -p "$T/.codemonkey/skills/demo_manual"
cat > "$T/.codemonkey/skills/demo_manual/manifest.json" <<'JSON'
{
  "name": "demo_manual",
  "spec": "hand-written candidate; never ran",
  "params": {"type": "object", "properties": {"msg": {"type": "string"}}},
  "probe": "echo demo ok",
  "provenance": {"run_id": "manual", "session_id": "", "taint_free": true},
  "status": "quarantined"
}
JSON
(cd "$T" && HOME="$T/home" uv run --project "$REPO" codemonkey skills list)
echo "exit=$?"

echo "=== (c) quarantined skills are NOT loaded ==="
(cd "$T" && HOME="$T/home" uv run --project "$REPO" python -c "
from codemonkey import skills
assert skills.load_admitted('.') == [], 'quarantined skill was loaded!'
print('load_admitted: [] (quarantined skills not loaded)')
")
echo "exit=$?"

echo "=== (d) skills --help ==="
(cd "$T" && HOME="$T/home" uv run --project "$REPO" codemonkey skills --help | head -8)
echo "exit=$?"
rm -rf "$T"
