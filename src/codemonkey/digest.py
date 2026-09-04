"""Run digest (loop21, cycle 58): one thread's story in plain text."""

from __future__ import annotations

from collections import Counter


def build_digest(thread_id: str) -> dict:
    from .journal import read_thread

    try:
        recs = read_thread(thread_id)
    except Exception:
        recs = []

    tools: Counter = Counter()
    commands: list[str] = []
    failures: list[dict] = []
    flags: list[str] = []
    for r in recs:
        if r.get("type") == "intent":
            tools[r.get("tool", "?")] += 1
        elif r.get("type") == "outcome":
            if r.get("status") == "error":
                failures.append({"tool": r.get("tool", "?"),
                                 "error_class": r.get("error_class") or "error",
                                 "detail": (str(r.get("output", "")) or "")[:120]})
            if "model_unload_fallback" in str(r.get("status", "")):
                flags.append("route: model_unload_fallback → " + str(r.get("output", ""))[:60])
            if r.get("error_class") == "schema_mismatch":
                flags.append("args: schema_mismatch — " + str(r.get("output", ""))[:60])
    return {
        "thread": thread_id,
        "tool_counts": dict(tools),
        "failures": failures,
        "flags": flags,
        "records": len(recs),
    }


def render_digest(d: dict) -> str:
    lines = [f"# run digest: {d['thread']}"]
    if d.get("tool_counts"):
        tc = ", ".join(f"{k}×{v}" for k, v in sorted(d["tool_counts"].items(),
                                                      key=lambda kv: -kv[1]))
        lines.append(f"tools: {tc}")
    else:
        lines.append("tools: none")
    if d["failures"]:
        lines.append("failures:")
        for f in d["failures"]:
            lines.append(f"  - {f['tool']} [{f['error_class']}]: {f['detail']}")
    else:
        lines.append("failures: none")
    if d.get("flags"):
        lines.append("flags:")
        lines.extend(f"  - {f}" for f in d["flags"])
    lines.append(f"journal records: {d['records']}")
    return "\n".join(lines)


def digest_recent(n: int) -> list[dict]:
    """Digest the N most recent threads (newest first)."""
    from .journal import list_threads

    threads = [t for t in list_threads() if isinstance(t, str)]
    out = []
    for tid in list(reversed(threads))[:n]:
        try:
            out.append(build_digest(tid))
        except Exception:
            continue
    return out


def render_multi(digests: list[dict]) -> str:
    parts = [render_digest(d) for d in digests]
    if not parts:
        return "(no threads)"
    return ("\n\n---\n\n").join(parts)
