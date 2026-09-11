#!/usr/bin/env bash
# CYCLE loop45-final — break-verification of the register's OTHER three
# claimed controls (added C106; break runs recorded here at the v4.0 close so
# "goes red when it stops being true" is demonstrated, not assumed):
#   D. a row marked UNVALIDATED                      (test_no_row_is_unvalidated)
#   E. a row carrying no known status                (test_every_row_carries_a_status)
#   F. an active row naming a module that is gone    (test_no_active_row_names_a_module_that_does_not_exist)
set -u
cd "$(dirname "$0")/../.."
REG=build/CAPABILITY_REGISTER.md
OUT=build/probes/loop45final-register-controls2.out
: > "$OUT"
sha() { shasum -a 256 "$REG" | cut -d' ' -f1; }

BEFORE=$(sha)
echo "baseline sha256: $BEFORE" | tee -a "$OUT"

run_test() {
  uv run pytest -q tests/test_register.py --tb=line 2>&1 | tail -3 | tee -a "$OUT"
}

echo "=== BREAK D: 'stuck' row status -> UNVALIDATED ===" | tee -a "$OUT"
cp "$REG" /tmp/reg2.break.bak
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
old = "| stuck | PROVEN-LIVE |"
assert t.count(old) == 1, "break D anchor not unique"
open(p, "w").write(t.replace(old, "| stuck | UNVALIDATED |"))
PY
run_test
cp /tmp/reg2.break.bak "$REG"

echo "=== BREAK E: 'stuck' row status -> a word that is no status ===" | tee -a "$OUT"
cp "$REG" /tmp/reg2.break.bak
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
old = "| stuck | PROVEN-LIVE |"
assert t.count(old) == 1
open(p, "w").write(t.replace(old, "| stuck | BROKEN |"))
PY
run_test
cp /tmp/reg2.break.bak "$REG"

echo "=== BREAK F: active row for a module that does not exist ===" | tee -a "$OUT"
cp "$REG" /tmp/reg2.break.bak
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]
t = open(p).read()
anchor = "## Active modules\n\n| module | status | entry probe |\n|---|---|---|\n"
assert t.count(anchor) == 1, "break F anchor not unique"
open(p, "w").write(t.replace(anchor, anchor + "| ghost_module | PROVEN-LIVE | none |\n"))
PY
run_test
cp /tmp/reg2.break.bak "$REG"

AFTER=$(sha)
echo "restored sha256: $AFTER" | tee -a "$OUT"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "RESTORE OK (hash identical)" | tee -a "$OUT"
else
  echo "RESTORE MISMATCH" | tee -a "$OUT"; exit 1
fi
echo "=== final re-run on the restored artifact (must be green) ===" | tee -a "$OUT"
run_test
