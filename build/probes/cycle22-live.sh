#!/usr/bin/env bash
# Cycle 22 LIVE (best-effort, BLOCKED-tolerant): two identical-prefix runs;
# raw wall-clock recorded. No claim made if numbers do not separate.
set -u
KEY=$(python3 -c "import yaml; c=yaml.safe_load(open('/Users/bharris/.hermes/config.yaml')); print([p['api_key'] for p in c.get('custom_providers',[]) if p.get('name')=='neuralwatt'][0])")
export CODEMONKEY_UNBLOCK2_KEY="$KEY" CODEMONKEY_PROVIDER=unblock2
cd ~/Programs/CodeMonkey || exit 1
OUT=build/probes/cycle22-timings.txt
: > "$OUT"
echo "# cycle22 identical-prefix wall-clock (best-effort; no claim implied)" >> "$OUT"
echo "# prompt: identical short prompt, same model (kimi-k2.7-code via 3459)" >> "$OUT"
for i in 1 2 3 4; do
  S=$(date +%s)
  uv run codemonkey exec --ephemeral "Reply with the single word: cache-test" > /dev/null 2>&1
  E=$(date +%s)
  echo "run $i wall: $((E - S))s" >> "$OUT"
done
cat "$OUT"
