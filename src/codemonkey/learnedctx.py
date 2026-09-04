"""Learned context assembly (R36).

Assembly as scoring, not a fixed recipe: candidates from four sources
(project-context, instructions, memory, repo-map) are ranked by a learned
utility = (grammar class weight) × (task-term overlap) × (loop-35 recency
decay). Top fragments fill the budget greedily. Pure + deterministic; the
model is never consulted at assembly time (no self-confirmation).
"""

from __future__ import annotations

import re
import time

CLASS_WEIGHTS = {
    "memory": 1.2,        # curated and small
    "instructions": 1.1,  # operator intent
    "project_context": 1.0,
    "repo_map": 0.6,      # dense, often large
}

_DATE_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2})\]")


def _terms(text: str, min_len: int = 4) -> set:
    return {w.lower() for w in re.findall(r"\w+", text or "") if len(w) >= min_len}


def _recency_weight(text: str, now: float | None = None,
                    half_life_days: float = 14.0) -> float:
    now = now if now is not None else time.time()
    m = _DATE_RE.search(text or "")
    if not m:
        return 1.0
    import datetime as dt

    try:
        age = (now - dt.datetime.strptime(m.group(1), "%Y-%m-%d").timestamp()) / 86400
    except ValueError:
        return 1.0
    return 0.5 ** (max(0.0, age) / half_life_days)


def assemble(task: str, fragments: list, *, token_budget: int = 600,
             top_per_source: int = 3, now: float | None = None) -> dict:
    """fragments: [{source, text}]. Greedy fill by utility; keeps original
    selection order for stable injection."""
    task_terms = _terms(task)
    scored = []
    for i, f in enumerate(fragments):
        text = str(f.get("text", ""))
        cweight = CLASS_WEIGHTS.get(f.get("source", ""), 1.0)
        terms = _terms(text)
        overlap = (len(terms & task_terms) / len(task_terms)
                   if terms and task_terms else 0.0)
        rw = _recency_weight(text, now=now)
        utility = cweight * (0.25 + 0.75 * overlap) * (0.5 + 0.5 * rw)
        scored.append({"index": i, "source": f.get("source", "?"),
                       "utility": round(utility, 4),
                       "words": len(text.split()), "text": text})
    ranked = sorted(scored, key=lambda s: -s["utility"])
    used = 0
    per_source: dict = {}
    keep_idx: list = []
    dropped: list = []
    for s in ranked:
        if per_source.get(s["source"], 0) >= top_per_source:
            dropped.append(s)
            continue
        if used + s["words"] <= token_budget:
            keep_idx.append(s["index"])
            per_source[s["source"]] = per_source.get(s["source"], 0) + 1
            used += s["words"]
        else:
            dropped.append(s)
    util_by_idx = {s["index"]: s["utility"] for s in scored}
    selected = []
    for i in sorted(keep_idx):
        frag = dict(fragments[i])
        frag["utility"] = util_by_idx[i]
        selected.append(frag)
    return {"selected": selected, "dropped": dropped,
            "budget": token_budget, "used": used}
