"""Step-level scoring + rubrics (R33, generative-verifier substrate).

A rubric = ordered checklist of boolean graders (regex/containment/predicate)
attached to a task; score_rubric returns per-step pass/fail with evidence.
Used by eval tasks (per-step detail) and review rounds. Generative step
(making the model PROPOSE the rubric) lands as eval-suite authoring sugar;
the scoring core is deterministic — model calls stay out of the grader.
"""

from __future__ import annotations

import re


def score_rubric(reply: str, rubric: list[dict]) -> dict:
    """rubric steps: {"id", "kind": contains|regex|absent, "value"}.
    Returns {steps: [...], passed: bool, score: float}."""
    steps = []
    for step in rubric or []:
        sid = step.get("id", "?")
        kind = step.get("kind", "contains")
        value = str(step.get("value", ""))
        low = reply.lower()
        if kind == "contains":
            ok = value.lower() in low
        elif kind == "regex":
            ok = re.search(value, reply) is not None
        elif kind == "absent":
            ok = value.lower() not in low
        else:
            ok = False
        steps.append({"id": sid, "kind": kind, "ok": ok})
    n = len(steps) or 1
    passed = all(s["ok"] for s in steps)
    return {"steps": steps, "passed": passed,
            "score": round(sum(1 for s in steps if s["ok"]) / n, 3)}


def rubric_from_yaml_steps(steps: list[str]) -> list[dict]:
    """Authoring sugar: ["contains: hello", "regex: \\d+"] → structured."""
    out: list[dict] = []
    for i, s in enumerate(steps or []):
        kind, _, value = s.partition(":")
        out.append({"id": f"step{i + 1}", "kind": kind.strip(), "value": value.strip()})
    return out
