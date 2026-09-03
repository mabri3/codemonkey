# cycle29 KV-cache telemetry live probe
# home llama.cpp returns timings.cache_n AND usage.prompt_tokens_details.cached_tokens
# streaming required stream_options.include_usage (added; llama.cpp honors it)
# --cost-summary live: cache: 5646/5680 tokens (99%) on repeated prefix
# result: PASS (7/7 tests + live)
