"""Delegate role presets (loop24, cycle 61).

role_presets config: role → {provider, model}. delegate resolves the preset
before spawning so critic/verifier can run on different local models; the
application is journaled (loop-17 route records make it measurable). Unknown
roles fall through to the default model.
"""

from __future__ import annotations

from typing import Optional


def resolve_role_preset(presets: Optional[dict], role: str,
                        *, default_provider: str = "local",
                        default_model: str = "") -> dict:
    """{provider, model, preset: name-or-''}."""
    p = (presets or {}).get(role)
    if isinstance(p, dict) and (p.get("provider") or p.get("model")):
        return {"provider": p.get("provider", default_provider),
                "model": p.get("model", default_model),
                "preset": role}
    return {"provider": default_provider, "model": default_model, "preset": ""}


def apply_to_cmd(cmd_args: dict, resolved: dict) -> dict:
    """Overlay resolved provider/model into a delegate CLI arg dict."""
    out = dict(cmd_args or {})
    if resolved.get("provider"):
        out["provider"] = resolved["provider"]
    if resolved.get("model"):
        out["model"] = resolved["model"]
    return out
