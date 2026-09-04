"""Static model routing (loop17, cycle 53).

.176 serves 3 models behind one endpoint; routing evidence (LLMRouterBench
2601.07206) says routing decisions need task features, not vibes. This module
implements FIRST-MATCH static rules selecting provider+model per task:

  model_routing:
    - when: {tool_role: review}
      use: {provider: local, model: unsloth/Qwen3.6-35B-A3B-MTP-GGUF}
    - when: {prompt_glob: "*compliance*"}
      use: {provider: local, model: lmstudio-community/Qwen3.8-27B-GGUF}

`tool_role` matches the loop-11 delegation role framing; `prompt_glob` is a
case-insensitive fnmatch on the task prompt. No match → default provider.
Every applied route is journaled (route record) so eval can aggregate
per-route pass_rate/tokens (--route-stats).
"""

from __future__ import annotations

import fnmatch
from typing import Optional
from typing import Optional


def select_route(rules: list[dict], *, prompt: str = "",
                 tool_role: str = "",
                 default_provider: str = "local",
                 default_model: Optional[str] = None) -> dict:
    """Return {provider, model, rule_index or None} for the task."""
    for idx, rule in enumerate(rules or []):
        when = rule.get("when") or {}
        ok = True
        if "tool_role" in when and when["tool_role"] != tool_role:
            ok = False
        if ok and "prompt_glob" in when:
            import fnmatch as _f

            if not fnmatch.fnmatch(prompt.lower(), str(when["prompt_glob"]).lower()):
                ok = False
        if ok:
            use = rule.get("use") or {}
            return {"provider": use.get("provider", default_provider),
                    "model": use.get("model", default_model or ""),
                    "rule_index": idx}
    return {"provider": default_provider, "model": default_model or "",
            "rule_index": None}


def validate_rules(rules: list) -> Optional[str]:
    """Return an error string for invalid rules, else None."""
    if not isinstance(rules, list):
        return "model_routing must be a list"
    for i, rule in enumerate(rules):
        if not isinstance(rule, dict) or "when" not in rule or "use" not in rule:
            return f"model_routing[{i}] needs 'when' and 'use'"
        when = rule["when"]
        if not isinstance(when, dict) or not (
                "tool_role" in when or "prompt_glob" in when):
            return (f"model_routing[{i}].when must contain tool_role or "
                    f"prompt_glob")
        use = rule["use"]
        if not isinstance(use, dict) or not ("provider" in use or "model" in use):
            return f"model_routing[{i}].use must set provider and/or model"
    return None


def route_stats(results: dict) -> dict:
    """Aggregate eval results per route (per provider/model recorded per task)."""
    stats: dict[str, dict] = {}
    for t in results.get("tasks", []):
        key = f"{t.get('route_provider', '?')}/{t.get('route_model', '?')}"
        s = stats.setdefault(key, {"tasks": 0, "ok": 0, "tokens": 0})
        s["tasks"] += 1
        s["ok"] += 1 if t.get("ok") else 0
        s["tokens"] += int(t.get("total_tokens") or 0)
    for s in stats.values():
        s["pass_rate"] = round(s["ok"] / s["tasks"], 3) if s["tasks"] else 0.0
    return stats

