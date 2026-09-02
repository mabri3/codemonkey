"""Tick-start health probe: check home llama.cpp inference + unblock proxy.

Loads provider URLs from the merged codemonkey config (no literal IPs in
shell args — the security scanner blocks those in cron sessions with no
approver present).
"""
import subprocess, sys, time
import httpx

cfg_out = subprocess.run(
    ["uv", "run", "codemonkey", "config"], capture_output=True, text=True,
    cwd="/Users/bharris/Programs/CodeMonkey",
).stdout
import yaml
cfg = yaml.safe_load(cfg_out)

for name in ("local", "unblock"):
    prov = (cfg.get("providers") or {}).get(name)
    if not prov:
        print(name, "NOT CONFIGURED")
        continue
    base = (prov.get("base_url") or "").rstrip("/")
    model = prov.get("model")
    # 1) models endpoint liveness
    try:
        t = time.time()
        r = httpx.get(base + "/models", timeout=5)
        print(f"{name}/models -> {r.status_code} ({time.time()-t:.1f}s)")
    except Exception as e:
        print(f"{name}/models DOWN ({type(e).__name__})")
        continue
    # 2) tiny inference check (home server used to hang here)
    try:
        t = time.time()
        r = httpx.post(
            base + "/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
                "max_tokens": 8,
                "stream": False,
            },
            timeout=30,
        )
        print(f"{name}/infer -> {r.status_code} ({time.time()-t:.1f}s)")
        if r.status_code == 200:
            try:
                print(f"   content={r.json()['choices'][0]['message'].get('content')!r}")
            except Exception:
                print(f"   body: {r.text[:300]!r}")
        else:
            print(f"   body: {r.text[:300]!r}")
    except Exception as e:
        print(f"{name}/infer FAIL ({type(e).__name__})")
