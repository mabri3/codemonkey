#!/usr/bin/env bash
# CYCLE 83 R-I probe — the admission gate through the RELEASED BINARY.
#   demo_ok  : probe exit 0  -> admitted, journal skill.admitted{probe_exit:0}
#   demo_bad : probe exit 3  -> refused, stays quarantined, stderr journaled
#   demo_ok  : probe now false -> re-admit evicts it (R-A)
set -u
cd "$(dirname "$0")/../.."
REPO=$(pwd)
T=$(mktemp -d)
mkdir -p "$T/home" "$T/.codemonkey/skills/demo_ok" "$T/.codemonkey/skills/demo_bad"

cat > "$T/.codemonkey/skills/demo_ok/manifest.json" <<'JSON'
{"name": "demo_ok", "spec": "passes its probe", "params": {"type": "object", "properties": {}},
 "probe": "echo gate_ok", "provenance": {"run_id": "r1", "session_id": "s1", "taint_free": true},
 "status": "quarantined"}
JSON
cat > "$T/.codemonkey/skills/demo_bad/manifest.json" <<'JSON'
{"name": "demo_bad", "spec": "fails its probe", "params": {"type": "object", "properties": {}},
 "probe": "echo womp >&2; exit 3", "provenance": {"run_id": "r1", "session_id": "s1", "taint_free": true},
 "status": "quarantined"}
JSON

run() { (cd "$T" && HOME="$T/home" uv run --project "$REPO" "$@"); }

echo "=== admit demo_ok (expect exit 0) ==="
run codemonkey skills admit demo_ok; echo "exit=$?"

echo "=== admit demo_bad (expect exit 1, stays quarantined) ==="
run codemonkey skills admit demo_bad; echo "exit=$?"

echo "=== skills list ==="
run codemonkey skills list; echo "exit=$?"

echo "=== journal (skills-$(basename "$T")) ==="
cat "$T/home/.codemonkey/journal/skills-$(basename "$T").jsonl" || echo "(no journal file)"

echo "=== re-admit demo_ok after its probe is made to fail (expect eviction) ==="
python3 - "$T" <<'PY'
import json, sys
p = sys.argv[1] + "/.codemonkey/skills/demo_ok/manifest.json"
m = json.load(open(p)); m["probe"] = "false"; json.dump(m, open(p, "w"))
PY
run codemonkey skills admit demo_ok; echo "exit=$?"
echo "=== skills list (expect evicted) ==="
run codemonkey skills list
rm -rf "$T"
