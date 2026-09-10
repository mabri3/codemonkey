"""Run build/conformance.py against a scripted endpoint (102F10 method).

`build/conformance.py`'s `live_probe` — the only probe that needs a reachable
endpoint — drives the binary and then asserts the SUCCESS-path event set:
`item.*` (the public projection of tool calls) and a `turn.completed` carrying
usage. Those are properties of OUR loop, not of a model: a scripted tool call
over real HTTP exercises exactly the same code path.

So this is the 102F10 split applied to loop 43's own gate rather than to the
A-sweep: the probe is ENDPOINT-GATED, and it can be retired with a run behind
it instead of sitting BLOCKED. It cannot prove a real model *chooses* a tool —
that clause stays named in the report.

Usage:  uv run python build/conformance_with_stub.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "build" / "sweep_endpoint_gated.py"

_spec = importlib.util.spec_from_file_location("sweep_driver", DRIVER)
assert _spec and _spec.loader, "cannot load the sweep driver"
driver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(driver)

# One scripted tool call, then a final answer: item.started/item.completed come
# from the call, usage comes from every turn.completed.
CALL = ('TOOL_CALL: {"name": "shell", "arguments": {"command": "echo conform"}}')
SCRIPT = {
    "model": "stub-model",
    "turns": ["conform-ok"],
    "rules": [{"contains": "echo conform", "reply": CALL, "once": True}],
}


def main() -> int:
    with driver.Stub(SCRIPT) as stub:
        print(f"# scripted endpoint: {stub.base_url}")
        proc = subprocess.run(
            [sys.executable, "build/conformance.py"],
            cwd=str(ROOT), env=stub.env(), capture_output=True, text=True)
    print(proc.stdout, end="")
    if proc.stderr.strip():
        print(proc.stderr, file=sys.stderr, end="")
    print(f"# conformance exit: {proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
