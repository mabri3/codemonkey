#!/usr/bin/env bash
# Live verify-gate probe (cycle 19): model breaks calc.py, verify_command runs
# pytest, the gate forces a corrective turn, tests end passing.
set -u
KEY=$(python3 -c "import yaml; c=yaml.safe_load(open('/Users/bharris/.hermes/config.yaml')); print([p['api_key'] for p in c.get('custom_providers',[]) if p.get('name')=='neuralwatt'][0])")
export CODEMONKEY_UNBLOCK2_KEY="$KEY"

D=$(mktemp -d)
cd "$D" || exit 1
git init -q .
mkdir tests
cat > test_calc.py << 'EOF'
from calc import add
def test_add():
    assert add(2, 3) == 5
EOF
cat > calc.py << 'EOF'
def add(a, b):
    return a + b
EOF

export CODEMONKEY_PROVIDER=unblock2
export CODEMONKEY_VERIFY_COMMAND="uv run --project $HOME/Programs/CodeMonkey pytest -q"
uv run --project ~/Programs/CodeMonkey codemonkey exec --ephemeral --approval never \
  "Edit calc.py with edit_file: change 'return a + b' to 'return a + b + 1'. After the verify command runs and FAILS, fix calc.py so the tests pass again. Reply GATE-OK when tests pass." \
  > /tmp/vg.out 2>/tmp/vg.err
echo "exit=$?"
echo "--- final line:"; tail -1 /tmp/vg.out
echo "--- verify notices:"; grep -c "verify" /tmp/vg.err || true
echo "--- final file:"; cat calc.py
echo "--- tests now:"; uv run --project ~/Programs/CodeMonkey pytest -q 2>&1 | tail -1
