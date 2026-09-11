#!/usr/bin/env bash
# CYCLE 109 break-verification — the admitted-gate is the load-bearing part of
# the byte-diff claim. Break it (load_admitted stops filtering status) and the
# discriminating tests MUST go red; restore and they must go green again,
# hash-identical. A run that stays green under this break is VOID and means
# the tests do not pin the property.
set -u
REPO=/Users/bharris/Programs/CodeMonkey
F="$REPO/src/codemonkey/playbook.py"
BAK=$(mktemp)
cp "$F" "$BAK"
BEFORE=$(shasum -a 256 "$F" | cut -d' ' -f1)
FAIL=0

echo "--- applying the break (admitted-gate dropped) ---"
python3 - <<'PY'
from pathlib import Path
p = Path("/Users/bharris/Programs/CodeMonkey/src/codemonkey/playbook.py")
s = p.read_text()
orig = '    return [e for e in list_entries(workdir) if e.get("status") == "admitted"]'
assert orig in s, "anchor not found — refusing to patch blind"
s = s.replace(orig, '    return list_entries(workdir)  # BREAK: gate dropped')
p.write_text(s)
print("break applied: load_admitted no longer filters status")
PY

echo "--- break must take effect (live check, else the run is VOID) ---"
(cd "$REPO" && uv run python -c "
from pathlib import Path
import tempfile
from codemonkey import playbook
tmp = Path(tempfile.mkdtemp())
playbook.merge_deltas(tmp, [{'kind': 'strategy', 'section': 's', 'text': 'q',
                             'provenance': {'run_id': 'r', 'session_id': '',
                                            'taint_free': True}}])
rows = playbook.load_admitted(tmp)
assert len(rows) == 1, 'break did not take effect — VOID run'
print('break verified live: a quarantined entry now LOADS')
") || { echo "BREAK DID NOT TAKE EFFECT — void run, restoring"; cp "$BAK" "$F"; exit 2; }

echo "--- the discriminating tests under the break (must go RED) ---"
OUT=$(cd "$REPO" && uv run pytest -q tests/test_playbook_injection.py 2>&1 | tail -3)
echo "$OUT"
echo "$OUT" | grep -q "passed" && ! echo "$OUT" | grep -q "failed" && { echo "VOID: stayed green under the break"; FAIL=1; }
echo "$OUT" | grep -q "failed" || { echo "expected failures did not appear"; FAIL=1; }

echo "--- restoring ---"
cp "$BAK" "$F"
AFTER=$(shasum -a 256 "$F" | cut -d' ' -f1)
echo "before: $BEFORE"
echo "after:  $AFTER"
[ "$BEFORE" = "$AFTER" ] || { echo "RESTORE MISMATCH"; FAIL=1; }

echo "--- green again ---"
OUT2=$(cd "$REPO" && uv run pytest -q tests/test_playbook_injection.py 2>&1 | tail -2)
echo "$OUT2"
echo "$OUT2" | grep -q "7 passed" || { echo "restore did not go green"; FAIL=1; }

echo
if [ "$FAIL" -eq 0 ]; then echo "CYCLE109 BREAK-VERIFY: PASS"; else echo "CYCLE109 BREAK-VERIFY: FAIL"; fi
exit "$FAIL"
