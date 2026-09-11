"""skill_create — write a QUARANTINED candidate skill (loop46, cycle 84).

This tool is how a run leaves something behind for the next one — and the
only reason it is safe to expose is that it cannot do more than that: it
writes into the quarantined store (`.codemonkey/skills/<name>/`), the store
is gitignored by construction, nothing loads it until the mechanical
admission gate (`codemonkey skills admit`) has run the candidate's own
self-probe in the sandbox, and one command revokes it.

Two gates must BOTH be open for this tool to write anything:

1. **Strategy** — `strategies.skills` must be `learn` (default `off`). Under
   `use`, a `skill_create` call is a tool ERROR, not a write: a run that is
   allowed to use the library is not thereby allowed to extend it.
2. **Sandbox** — `skill_create` is classified as a write tool, so it is
   denied at `read-only` like any other mutating call.

Provenance is recorded from the run's own context; when the run cannot
attest that the producing turn was taint-free (cycle 85 wires the tracker),
the flag is recorded FALSE — the field never claims a cleanliness the run
cannot back.
"""

from __future__ import annotations

from .base import ToolResult, _err

SPEC = ("skill_create(name, spec, probe, params={}, tool_src) -> write a "
        "QUARANTINED candidate skill (requires strategies.skills=learn; "
        "admission is a separate mechanical gate)")

PARAMS = {
    "type": "object",
    "properties": {
        "name": {"type": "string",
                 "description": "lowercase identifier (letters, digits, _)"},
        "spec": {"type": "string",
                 "description": "one-line description advertised to future runs"},
        "probe": {"type": "string",
                  "description": "the skill's own self-probe command; exit 0 "
                                 "is required for admission"},
        "params": {"type": "object",
                   "description": "JSON-Schema (type: object) of the skill's arguments"},
        "tool_src": {"type": "string",
                     "description": "python source of tool.py: def run(args, ctx) -> result"},
    },
    "required": ["name", "spec", "probe"],
}


def run(args: dict, ctx) -> ToolResult:
    from .. import skills as skills_mod
    from ..strategies import select_strategy

    extra = getattr(ctx, "extra", None) or {}
    try:
        strategy = select_strategy("skills", extra.get("config"))
    except Exception:
        strategy = "off"
    if strategy != "learn":
        return ToolResult(
            output=(f"error: skill_create requires strategies.skills=learn "
                    f"(effective: {strategy}) — a 'use' run cannot extend the "
                    f"library"),
            ok=False)

    prov = {
        "run_id": str(extra.get("run_id") or "unknown"),
        "session_id": str(extra.get("session_id") or ""),
        # cycle 85 obligation: thread the turn's real taint state in here.
        # Until a tracker attests cleanliness, the field says FALSE — never
        # a claimed clean run.
        "taint_free": bool(extra.get("taint_free", False)),
    }
    man = {
        "name": str(args.get("name", "")).strip(),
        "spec": str(args.get("spec", "")).strip(),
        "params": args.get("params") or {"type": "object", "properties": {}},
        "probe": str(args.get("probe", "")).strip(),
        "provenance": prov,
        "status": "quarantined",
    }
    try:
        path = skills_mod.write_manifest(
            ctx.workdir, man, tool_src=args.get("tool_src") or None)
    except skills_mod.SkillError as exc:
        return ToolResult(output=f"error: skill_create refused: {exc}", ok=False)
    except Exception as exc:  # never raise into the loop
        return _err(exc)
    return ToolResult(
        output=(f"quarantined skill written: {man['name']} -> {path} "
                f"(status: quarantined; NOT loadable until "
                f"`codemonkey skills admit {man['name']}` passes its probe)"))
