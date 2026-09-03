"""Secret redaction across durable stores (loop16, cycle 49).

Hardening pass: eval stdout excerpts and journal `output` fields are scanned
for configured API key values (and key-shaped strings) and the matches are
replaced with [REDACTED]. Applied at write time by the stores' callers and
available as a repair pass (`codemonkey redact` no-op when clean).
"""

from __future__ import annotations

import re

_KEY_SHAPED = re.compile(r"\b(sk|rk)-[A-Za-z0-9_-]{20,}\b")


def needles_from_config(cfg: dict) -> list[str]:
    """Actual secret values from the config (api_key_env values present in env
    or inline). Only non-empty values are needles."""
    needles = []
    for pconf in (cfg.get("providers") or {}).values():
        env_name = pconf.get("api_key_env")
        if env_name:
            import os

            val = os.environ.get(env_name)
            if val and len(val) >= 12:
                needles.append(val)
    return needles


def redact_text(text: str, needles: list[str]) -> tuple[str, int]:
    """Replace each needle (and key-shaped strings) with [REDACTED].
    Returns (redacted, hits)."""
    hits = 0
    out = text
    for needle in needles:
        if needle in out:
            hits += out.count(needle)
            out = out.replace(needle, "[REDACTED]")
    out, n = _KEY_SHAPED.subn("[REDACTED]", out)
    hits += n
    return out, hits


def redact_eval_results(results: dict, needles: list[str]) -> tuple[dict, int]:
    """Redact stdout/task-text fields in an eval results dict (in place)."""
    total = 0
    for t in results.get("tasks", []):
        for field in ("stdout",):
            if isinstance(t.get(field), str):
                t[field], n = redact_text(t[field], needles)
                total += n
    return results, total


def redact_journal_file(path, needles: list[str]) -> int:
    """Repair pass over one journal JSONL file. Returns hits replaced."""
    import json
    import os

    try:
        lines = path.read_text().splitlines()
    except OSError:
        return 0
    out_lines, total = [], 0
    changed = False
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue
        if isinstance(rec.get("output"), str):
            new, n = redact_text(rec["output"], needles)
            if n:
                rec["output"] = new
                total += n
                changed = True
        newline = json.dumps(rec)
        if newline != line:
            changed = True
        out_lines.append(newline if changed else line)
    if total:
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(out_lines) + "\n")
        os.replace(tmp, path)
    return total
