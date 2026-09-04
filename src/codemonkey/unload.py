"""Unload-fallback rerouting (loop18, cycle 54).

The LM Studio-class single-slot server unloads the resident model when a
routed request names a different model (loop-17 incident: 400
"No model loaded. Call POST /inference/load first."). This module classifies
that response so exec can retry ONCE against the default provider/model
instead of failing the run.

Selection criteria: the error body/exception text mentions the model not
being loaded (server-side state), NOT an auth/param problem.
"""

from __future__ import annotations


def is_model_unloaded_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        ("no model loaded" in text)
        or ("model not loaded" in text)
        or ("call post /inference/load" in text)
        or ("please load the model" in text)
        or ("no model is loaded" in text)
    )


def fallback_route(default_provider: str, default_model: str | None) -> dict:
    """The fallback route applied after an unload failure."""
    return {"provider": default_provider,
            "model": default_model or "",
            "reason": "model_unload_fallback"}
