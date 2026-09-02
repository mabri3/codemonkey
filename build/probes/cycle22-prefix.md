# cycle22 prefix-stability + cache_prompt probe — 2026-09-02T12:09:22.648521
# unit: system byte-identical across turns incl. after tool results and after
# forced compaction (only the message tail shrinks); cache_prompt present in
# the openai body when enabled, absent when disabled; anthropic source has no
# cache_prompt (body unchanged).
# LIVE (best-effort): 4 identical-prefix runs 2s/1s/1s/1s — raw numbers in
# build/probes/cycle22-timings.txt; NO performance claim made (numbers too
# coarse to separate cache hits from noise).
# results: PASS (unit contract); LIVE recorded no-claim
