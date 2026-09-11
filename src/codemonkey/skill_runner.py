"""Child-process runner for an admitted skill (loop46, cycle 84).

Agent-authored code is NEVER imported into the agent's own process. When a
run calls an admitted skill, `skills.dispatch` spawns this module in a child
(`python -m codemonkey.skill_runner <tool.py> <args-json>`), the child
imports the skill's `tool.py` and calls its `run(args, ctx)` once, and the
child prints ONE JSON line: `{"ok": bool, "output": str, "error": str}`.
The parent parses that line; anything else (crash, garbage, timeout) is a
failed call — never a partially-trusted result.

The child's `ToolContext` is minimal on purpose: workdir + a fixed sandbox
level. The child is not a place where policy decisions happen; the PARENT
already ran the sandbox gate before spawning.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2:
        print(json.dumps({"ok": False, "output": "",
                          "error": "usage: python -m codemonkey.skill_runner "
                                   "TOOL_PY ARGS_JSON"}))
        return 2
    tool_path, args_json = argv[0], argv[1]

    from .sandbox import ToolContext

    ctx = ToolContext(workdir=Path.cwd(), sandbox="workspace-write")
    try:
        spec = importlib.util.spec_from_file_location("cm_skill_tool", tool_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {tool_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, "run", None)
        if not callable(fn):
            raise AttributeError("skill tool.py must define run(args, ctx)")
        result = fn(json.loads(args_json), ctx)
    except Exception as exc:  # the child reports, it never tracebacks to stdout
        print(json.dumps({"ok": False, "output": "", "error": str(exc)}))
        return 1

    if isinstance(result, dict):
        payload = {"ok": bool(result.get("ok", True)),
                   "output": str(result.get("output", "")),
                   "error": str(result.get("error", ""))}
    else:
        payload = {"ok": bool(getattr(result, "ok", False)),
                   "output": str(getattr(result, "output", "")),
                   "error": str(getattr(result, "error", ""))}
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
