# Loop 24 Research — Delegate Role Presets (CYCLE R24)

Date: 2026-09-03 · Method: carried evidence — the .176 server runs two live
models (Qwen3.8-27B dense, Qwen3.6-35B-A3B MoE); loop-11 shipped roles
(implementer/critic/verifier) but role→model mapping is manual per call.

## Finding
A `role_presets` config maps delegation roles to provider+model:
```yaml
role_presets:
  critic:  {provider: local, model: unsloth/Qwen3.6-35B-A3B-MTP-GGUF}
  verifier: {provider: local, model: unsloth/Qwen3.8-27B-GGUF}
```
`delegate(role=critic)` resolves the preset → route; journal records which
preset applied (alongside loop-17's route records). With loop-18 fallback +
affinity batching this is safe on single-slot servers.

## SELECTED
1. **CYCLE 61 — `role_presets`**: config table; delegate resolves role →
   provider/model before spawning (CLI flag passes model), preset application
   journaled; unknown role falls through to default model.
   verify: unit (≥5 tests: preset resolution, unknown role default,
   journal record, config default empty = no change, batch tasks
   per-role routed).
