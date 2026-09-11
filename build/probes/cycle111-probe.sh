#!/usr/bin/env bash
# CYCLE 111 probe (R-I, literal): the R-A consolidation through the CLI.
# `lessons` reads the playbook now; `playbook migrate-lessons` moves an old
# HOME store through the parity gate and archives it; the legacy verbs keep
# answering; the parity function goes red when a migrated entry is dropped.
set -u
REPO=/Users/bharris/Programs/CodeMonkey
T=$(mktemp -d)
W="$T/ws"
mkdir -p "$W" "$T/.codemonkey"
export HOME="$T"
FAIL=0

run_cm() { (cd "$W" && uv run --quiet --project "$REPO" codemonkey "$@"); }

cat > "$T/.codemonkey/lessons.json" <<'JSON'
[
 {"id": "les-1-1", "tags": {"tool": "shell", "error_class": "timeout"},
  "text": "use streaming deadlines for shell", "verified": true, "created": 1.0},
 {"id": "les-1-2", "tags": {"tool": "repo_map", "error_class": "parse"},
  "text": "repo_map chokes on generated dirs", "verified": true, "created": 2.0},
 {"id": "les-1-3", "tags": {"tool": "*", "error_class": "*"},
  "text": "draft: revisit retry policy", "verified": false, "created": 3.0}
]
JSON

echo "--- 1. lessons now reads the PLAYBOOK (empty) not the old HOME file ---"
out=$(run_cm lessons list); echo "$out"
[ "$out" = "(no lessons)" ] || { echo "FAIL step1"; FAIL=1; }

echo "--- 2. migrate through the parity gate ---"
out=$(run_cm playbook migrate-lessons); code=$?
echo "$out"; echo "exit=$code"
[ "$code" -eq 0 ] && echo "$out" | grep -q "migrated 3 lesson(s)" || { echo "FAIL step2"; FAIL=1; }
echo "$out" | grep -q "2 verified admitted" || { echo "FAIL step2 verified"; FAIL=1; }

echo "--- 3. legacy surface answers from the new store ---"
out=$(run_cm lessons list); echo "$out"
[ "$(echo "$out" | grep -c 'verified')" -eq 2 ] || { echo "FAIL step3 verified count"; FAIL=1; }
[ "$(echo "$out" | grep -c 'draft')" -eq 1 ] || { echo "FAIL step3 draft count"; FAIL=1; }
out=$(run_cm lessons retrieve "shell timeout issue"); echo "$out"
echo "$out" | grep -q "streaming deadlines" || { echo "FAIL step3 retrieve"; FAIL=1; }

echo "--- 4. old file archived (not destroyed); playbook shows lesson entries ---"
ls "$T/.codemonkey" | grep -q "lessons.json.migrated-" || { echo "FAIL step4 archive"; FAIL=1; }
[ ! -f "$T/.codemonkey/lessons.json" ] || { echo "FAIL step4 file still live"; FAIL=1; }
out=$(run_cm playbook list); echo "$out" | head -5
echo "$out" | grep -q "lesson/" || { echo "FAIL step4 playbook lesson kind"; FAIL=1; }
out=$(run_cm playbook stats); echo "$out"
echo "$out" | grep -q "admitted=2" || { echo "FAIL step4 stats"; FAIL=1; }

echo "--- 5. parity function sees a dropped entry (break check) ---"
(cd "$W" && uv run --quiet --project "$REPO" python - <<'PY'
from pathlib import Path
from codemonkey import playbook
ws = Path.cwd()
entries = [e for e in playbook.list_entries(ws) if e["kind"] == "lesson"]
assert len(entries) == 3, entries
verified = [e["text"] for e in entries if e["status"] == "admitted"]
assert len(verified) == 2
ids_before = {e["id"] for e in entries}
# simulate the drop the gate exists to catch
playbook.revoke(ws, [e for e in entries if e["status"] == "admitted"][0]["id"])
v = playbook.parity_violations(ws, verified_before=verified,
                               ids_before=ids_before,
                               source_texts={e["text"] for e in entries})
assert v and "missing" in v[0], v
print(f"parity after a simulated drop: {v[0]}")
print("(the gate sees it — the migration would refuse and roll back)")
PY
) || { echo "FAIL step5"; FAIL=1; }

echo
if [ "$FAIL" -eq 0 ]; then echo "CYCLE111 PROBE: PASS"; else echo "CYCLE111 PROBE: FAIL"; fi
exit "$FAIL"
