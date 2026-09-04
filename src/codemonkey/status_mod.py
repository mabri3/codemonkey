"""codemonkey status (loop15, cycle 48): operator surface.

One-shot aggregation over every durable store:
  jobs (progress), journal failure classes (recent), sessions count,
  latest eval baseline pass_rate, cost ledger totals, spill bytes.
"""

from __future__ import annotations

import json
from pathlib import Path


def _jobs_section() -> dict:
    from .jobs import list_jobs

    jobs = list_jobs()
    return {
        "count": len(jobs),
        "items": [{
            "id": j["id"],
            "goal": j.get("goal", "")[:60],
            "done": sum(1 for s in j.get("steps", []) if s.get("status") == "done"),
            "failed": sum(1 for s in j.get("steps", []) if s.get("status") == "failed"),
            "total": len(j.get("steps", [])),
        } for j in jobs[:10]],
    }


def _journal_section(threads: int = 5) -> dict:
    from .journal import class_summary, list_threads, read_thread

    classes: dict[str, int] = {}
    for tid in reversed(list_threads()[-threads:]):
        for cls, n in class_summary(read_thread(tid)).items():
            classes[cls] = classes.get(cls, 0) + n
    return {"threads_scanned": min(threads, len(list_threads())), "classes": classes}


def _sessions_section() -> dict:
    from .sessions import sessions_dir

    d = sessions_dir()
    n = sum(1 for _ in d.glob("*.jsonl"))
    return {"count": n}


def _eval_section(eval_dir: Path) -> dict:
    p = eval_dir / "baseline.json"
    if not p.is_file():
        return {"baseline": None}
    try:
        b = json.loads(p.read_text())
        return {"baseline": {"suite": b.get("suite"),
                             "pass_rate": b.get("pass_rate"),
                             "total_tokens": b.get("total_tokens")}}
    except (OSError, json.JSONDecodeError):
        return {"baseline": None}


def _cost_section() -> dict:
    from .cost import ledger_path

    p = ledger_path()
    try:
        ledger = json.loads(p.read_text())
        return {"runs": len(ledger.get("runs", [])),
                "total_tokens": ledger.get("total_tokens", 0),
                "total_turns": ledger.get("total_turns", 0)}
    except (OSError, json.JSONDecodeError):
        return {"runs": 0, "total_tokens": 0, "total_turns": 0}


def _spill_section() -> dict:
    from .spill import spill_dir

    d = spill_dir()
    files = list(d.glob("*.txt"))
    return {"files": len(files),
            "bytes": sum(f.stat().st_size for f in files if f.exists())}


def collect(eval_dir: Path) -> dict:
    return {
        "jobs": _jobs_section(),
        "journal": _journal_section(),
        "sessions": _sessions_section(),
        "eval": _eval_section(eval_dir),
        "cost": _cost_section(),
        "spill": _spill_section(),
    }


def render(status: dict) -> str:
    lines = []
    jobs = status.get("jobs", {})
    if jobs.get("count"):
        for j in jobs.get("items", []):
            lines.append(f"job {j['id']}: [{j['done']}/{j['total']}]"
                         f"{f' ({j[chr(102)+chr(97)+chr(105)+chr(108)+chr(101)+chr(100)]} failed)' if j['failed'] else ''}  {j['goal']}")
    else:
        lines.append("jobs: none")
    j = status.get("journal", {})
    classes = j.get("classes", {})
    if classes:
        cls = ", ".join(f"{k}: {v}" for k, v in sorted(classes.items()))
        lines.append(f"journal ({j.get('threads_scanned', 0)} recent): {cls}")
    else:
        lines.append("journal: clean")
    lines.append(f"sessions: {status.get('sessions', {}).get('count', 0)}")
    b = status.get("eval", {}).get("baseline")
    lines.append(f"eval baseline: {b['pass_rate'] if b else 'none'}"
                 + (f" ({b['suite']})" if b else ""))
    c = status.get("cost", {})
    lines.append(f"cost ledger: {c.get('total_tokens', 0)} tokens over {c.get('runs', 0)} runs")
    sp = status.get("spill", {})
    lines.append(f"spill: {sp.get('files', 0)} files, {sp.get('bytes', 0)} bytes")
    return "\n".join(lines)


def render_frame(data: dict, frame_no: int) -> str:
    """Pure function for watch cycles: timestamped frame."""
    import time as _t

    return (_t.strftime("%H:%M:%S") + "\n" + render(data))


def collect_latest_sessions(n: int) -> list[str]:
    """Session thread ids, newest first."""
    from .journal import list_threads as _lt

    return [t for t in _lt() if isinstance(t, str)][:n]
