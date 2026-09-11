#!/usr/bin/env bash
# CYCLE loop45-final — break-verification of the R-G/R-F annotation control
# (tests/test_register.py::test_loop38_45_rows_carry_local_published_gap_cost).
#
# Every break is applied to the REAL artifact (build/CAPABILITY_REGISTER.md),
# the control is run against the broken artifact, then the artifact is
# restored and the restore is hash-checked. Three branches of the "every"
# quantifier, one break each:
#   A. a module in the derived set loses its annotation row   (missing)
#   B. an annotation row exists for a module outside the set  (extra)
#   C. an annotation row loses a cell                         (incomplete)
set -u
cd "$(dirname "$0")/../.."
REG=build/CAPABILITY_REGISTER.md
OUT=build/probes/loop45final-annotation-breaks.out
: > "$OUT"
sha() { shasum -a 256 "$REG" | cut -d' ' -f1; }

BEFORE=$(sha)
echo "baseline sha256: $BEFORE" | tee -a "$OUT"

run_test() {
  uv run pytest -q tests/test_register.py --tb=line 2>&1 | tail -4 | tee -a "$OUT"
}

echo "=== BREAK A: delete the 'budgets' annotation row (missing branch) ===" | tee -a "$OUT"
cp "$REG" /tmp/reg.break.bak
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]
lines = open(p).read().splitlines(keepends=True)
out = [l for l in lines if not l.startswith("| budgets (loop44")]
assert len(out) == len(lines) - 1, "break A did not remove exactly one line"
open(p, "w").writelines(out)
PY
run_test
cp /tmp/reg.break.bak "$REG"

echo "=== BREAK B: add an annotation row for a module OUTSIDE the arc (extra branch) ===" | tee -a "$OUT"
cp "$REG" /tmp/reg.break.bak
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]
text = open(p).read()
anchor = "|---|---|---|---|---|\n"
assert text.count(anchor) == 1, "break B anchor not unique"
text = text.replace(anchor, anchor + "| lessons (loop17 · C13) | x | y | z | w |\n")
open(p, "w").write(text)
PY
run_test
cp /tmp/reg.break.bak "$REG"

echo "=== BREAK C: blank the f2p COST cell (incomplete-cell branch) ===" | tee -a "$OUT"
cp "$REG" /tmp/reg.break.bak
python3 - "$REG" <<'PY'
import sys
p = sys.argv[1]
text = open(p).read()
old = "per-arm tokens/wall in `render_f2p_table`; live costs pending"
assert text.count(old) == 1, "break C anchor not unique"
open(p, "w").write(text.replace(old, "-"))
PY
run_test
cp /tmp/reg.break.bak "$REG"

AFTER=$(sha)
echo "restored sha256: $AFTER" | tee -a "$OUT"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "RESTORE OK (hash identical)" | tee -a "$OUT"
else
  echo "RESTORE MISMATCH" | tee -a "$OUT"; exit 1
fi
echo "=== final re-run on the restored artifact (must be green) ===" | tee -a "$OUT"
run_test
