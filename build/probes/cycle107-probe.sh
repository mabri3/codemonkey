#!/usr/bin/env bash
# CYCLE 107 probe (R-I, literal): the playbook store through the RELEASED CLI.
# HOME and workspace both live in a tmp dir — the operator's ~/.codemonkey is
# untouched. Every step asserts its exit code; any mismatch fails the probe.
set -u
REPO="$HOME/../bharris/Programs/CodeMonkey"
REPO="/Users/bharris/Programs/CodeMonkey"
T=$(mktemp -d)
W="$T/ws"
mkdir -p "$W"
export HOME="$T"
FAIL=0

run_cm() { (cd "$W" && uv run --quiet --project "$REPO" codemonkey "$@"); }

step() { echo; echo "--- $1 ---"; }

step "1. list with no store (honest empty)"
out=$(run_cm playbook list); code=$?
echo "$out"; echo "exit=$code"
[ "$code" -eq 0 ] && echo "$out" | grep -q "no playbook entries" || { echo "FAIL step1"; FAIL=1; }

step "2. merge two valid deltas + one refusal"
cat > "$W/deltas.json" <<'JSON'
{"deltas": [
  {"kind": "strategy", "section": "tools",
   "text": "prefer rg over grep in this repo",
   "provenance": {"run_id": "probe-r1", "session_id": "probe-s1", "taint_free": true, "source": "operator:probe"}},
  {"kind": "pitfall", "section": "context",
   "text": "never rewrite accumulated context wholesale",
   "provenance": {"run_id": "probe-r1", "session_id": "probe-s1", "taint_free": true}},
  {"kind": "rant", "section": "tools", "text": "lol",
   "provenance": {"run_id": "probe-r1", "session_id": "probe-s1", "taint_free": true}}
]}
JSON
out=$(run_cm playbook merge deltas.json); code=$?
echo "$out"; echo "exit=$code"
[ "$code" -eq 0 ] && echo "$out" | grep -q "added=2 updated=0 refused=1" || { echo "FAIL step2"; FAIL=1; }

step "3. list shows 2 quarantined entries"
out=$(run_cm playbook list); code=$?
echo "$out"
[ "$code" -eq 0 ] || { echo "FAIL step3 exit"; FAIL=1; }
[ "$(echo "$out" | grep -c "quarantined")" -eq 2 ] || { echo "FAIL step3 count"; FAIL=1; }

step "4. in-process: quarantined entries do NOT load"
(cd "$W" && uv run --quiet --project "$REPO" python - <<'PY'
from pathlib import Path
from codemonkey import playbook
rows = playbook.load_admitted(Path.cwd())
assert rows == [], f"quarantined loaded: {rows}"
print(f"load_admitted -> {rows} (quarantined excluded)")
PY
) || { echo "FAIL step4"; FAIL=1; }

step "5. show one entry (full record)"
EID=$(run_cm playbook list | awk -F'\t' '$2=="quarantined"{print $1}' | head -1)
echo "entry: $EID"
out=$(run_cm playbook show "$EID"); code=$?
echo "$out"; echo "exit=$code"
[ "$code" -eq 0 ] && echo "$out" | grep -q "probe-r1" || { echo "FAIL step5"; FAIL=1; }

step "6. admit -> loads; re-merge -> counter bumps, bytes stable"
out=$(run_cm playbook admit "$EID"); echo "$out"
before=$(run_cm playbook show "$EID" | sed -n 's/^  text:     //p')
run_cm playbook merge deltas.json >/dev/null
after=$(run_cm playbook show "$EID" | sed -n 's/^  text:     //p')
count=$(run_cm playbook show "$EID" | sed -n 's/^  counter:  \([0-9]*\).*/\1/p')
echo "text before: $before"; echo "text after:  $after"; echo "counter: $count"
[ "$before" = "$after" ] || { echo "FAIL step6 text drifted"; FAIL=1; }
[ "$count" = "2" ] || { echo "FAIL step6 counter"; FAIL=1; }
(cd "$W" && uv run --quiet --project "$REPO" python - <<'PY'
from pathlib import Path
from codemonkey import playbook
rows = playbook.load_admitted(Path.cwd())
assert len(rows) == 1 and rows[0]["status"] == "admitted", rows
print(f"load_admitted -> {len(rows)} admitted (the re-merge changed no bytes it loads)")
PY
) || { echo "FAIL step6 load"; FAIL=1; }

step "7. revoke in one command -> gone"
out=$(run_cm playbook revoke "$EID"); code=$?
echo "$out"; echo "exit=$code"
[ "$code" -eq 0 ] || { echo "FAIL step7"; FAIL=1; }
out=$(run_cm playbook show "$EID" 2>&1); code=$?
echo "$out"; echo "show-after-revoke exit=$code"
[ "$code" -eq 2 ] || { echo "FAIL step7 show-after"; FAIL=1; }
[ "$(run_cm playbook list | grep -c 'quarantined\|admitted')" -eq 1 ] || { echo "FAIL step7 list"; FAIL=1; }

step "8. journal carries the acts"
(cd "$W" && uv run --quiet --project "$REPO" python - <<'PY'
from pathlib import Path
from codemonkey import journal
thread = "playbook-ws"
recs = journal.read_thread(thread) if hasattr(journal, "read_thread") else []
types = [r.get("type") for r in recs]
print(f"journal[{thread}] types: {types}")
assert "playbook.merged" in types, "no playbook.merged journaled"
assert "playbook.revoked" in types, "no playbook.revoked journaled"
PY
) || { echo "FAIL step8"; FAIL=1; }

echo
if [ "$FAIL" -eq 0 ]; then echo "CYCLE107 PROBE: PASS"; else echo "CYCLE107 PROBE: FAIL"; fi
exit "$FAIL"
