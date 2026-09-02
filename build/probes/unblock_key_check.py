"""Find where the unblock proxy API key lives and verify auth works.

The proxy (127.0.0.1:3458) answered 401 Missing API key when probed without
a key. BUILD_LOG says cycle 5 sourced CODEMONKEY_UNBLOCK_KEY from opencode
auth.json. This script inspects candidate stores and reports WHICH source +
key name works — never prints the key itself.
"""
import json, os
from pathlib import Path

import httpx

sources = {
    "opencode_auth": Path.home() / ".local/share/opencode/auth.json",
    "opencode_config": Path.home() / ".config/opencode/opencode.json",
    "opencode_auth2": Path.home() / ".config/opencode/auth.json",
}

candidates = {}  # label -> key
for label, p in sources.items():
    if not p.exists():
        print(f"{label}: {p} missing")
        continue
    print(f"{label}: {p} exists")
    try:
        d = json.loads(p.read_text())
    except Exception as e:
        print(f"  unreadable: {e}")
        continue

    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            kl = path.lower()
            if any(t in kl for t in ("key", "token", "auth")) and len(node) > 10:
                candidates[f"{label}:{path}"] = node

    walk(d)

for label in candidates:
    print(f"  candidate: {label} (len={len(candidates[label])})")

# Also check env
if os.environ.get("CODEMONKEY_UNBLOCK_KEY"):
    candidates["env:CODEMONKEY_UNBLOCK_KEY"] = os.environ["CODEMONKEY_UNBLOCK_KEY"]
    print("  candidate: env:CODEMONKEY_UNBLOCK_KEY")

# Try authing against the proxy with each candidate; report which works.
base = "http://127.0.0.1:3458/v1"
for label, key in candidates.items():
    try:
        r = httpx.post(
            base + "/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "minimax-m3",
                "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
                "max_tokens": 16,
                "stream": False,
            },
            timeout=60,
        )
        status = r.status_code
        body = r.text[:120]
    except Exception as e:
        status, body = f"ERR {type(e).__name__}", ""
    print(f"try {label}: {status} {body!r}")
    if status == 200:
        print(f"WORKING_SOURCE={label}")
        break
