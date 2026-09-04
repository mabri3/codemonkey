"""Tool-argument validation gate (loop20, cycle 57).

The 51F1 fix made the wire schema honest; this closes the dispatch side.
Validate tool args against a compact PARAMS table (required keys, types,
strict unknown-key mode) BEFORE execution. A mismatch returns a structured
{ok: False, error_class: schema_mismatch, detail} result that the loop feeds
back through the existing self-heal corrective path (machine-readable, so
the model can fix the call instead of dying on a KeyError).
"""

from __future__ import annotations

from typing import Optional

# per-tool contract: required keys, allowed optional keys + types
PARAMS: dict[str, dict] = {
    "read_file": {"required": ["path"], "types": {"path": str, "offset": int, "limit": int}},
    "write_file": {"required": ["path", "content"], "types": {"path": str, "content": str}},
    "edit_file": {"required": ["path"], "types": {"path": str, "old_string": str,
                                                  "new_string": str, "replace_all": bool}},
    "list_dir": {"required": [], "types": {"path": str}},
    "glob": {"required": ["pattern"], "types": {"pattern": str, "path": str, "limit": int}},
    "search": {"required": ["pattern"], "types": {"pattern": str, "path": str,
                                                  "file_glob": str, "limit": int}},
    "shell": {"required": ["command"], "types": {"command": str, "timeout": int}},
    "delegate": {"required": ["task"], "types": {"task": str, "role": str, "sandbox": str}},
    "delegate_batch": {"required": ["tasks"], "types": {"tasks": list, "max_delegates": int}},
    "update_plan": {"required": [], "types": {"steps": list}},
    "web_fetch": {"required": ["url"], "types": {"url": str}},
    "update_memory": {"required": [], "types": {"path": str, "content": str}},
    "job_update": {"required": [], "types": {"job_id": str, "step_id": str, "status": str}},
}


def validate_args(tool: str, args: dict, *, strict: bool = False) -> Optional[dict]:
    """None = valid. Otherwise:
    {ok: False, error_class: 'schema_mismatch', detail: <field-level>}.
    strict mode additionally rejects keys the tool doesn't declare."""
    spec = PARAMS.get(tool)
    if spec is None:
        return None  # tools without a contract stay pass-through
    if not isinstance(args, dict):
        return {"ok": False, "error_class": "schema_mismatch",
                "detail": f"{tool}: arguments must be an object, got {type(args).__name__}"}
    missing = [k for k in spec["required"] if k not in args]
    if missing:
        return {"ok": False, "error_class": "schema_mismatch",
                "detail": f"{tool}: missing required argument(s): {', '.join(missing)}"}
    for k, want in spec["types"].items():
        if k in args and not isinstance(args[k], want):
            return {"ok": False, "error_class": "schema_mismatch",
                    "detail": f"{tool}: argument '{k}' must be {want.__name__}, "
                              f"got {type(args[k]).__name__}"}
    if strict:
        unknown = [k for k in args if k not in spec["types"]
                   and k not in spec["required"]]
        if unknown:
            return {"ok": False, "error_class": "schema_mismatch",
                    "detail": f"{tool}: unknown argument(s): {', '.join(unknown)}"}
    return None
