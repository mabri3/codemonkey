"""Failure taxonomy (loop 39, cycle 88): journal records → AgentRx labels.

Maps this repo's observable failure signals onto the published nine-category
framing (AgentRx, adopted verbatim by AgentAtlas instead of re-derived)
using deterministic rules over (tool, error_class, status, output) — no LLM
judge. Four categories map per-record; two more (looping-over-action,
recovery-failure) are trajectory properties owned by the cycle-89 stuck
detector, not single records; three are honestly unmappable by rule:

- goal-misinterpretation: needs intent comparison (no intent object exists)
- unsafe-trust-of-external-content: needs a trust boundary the tools lack
- state-contamination: needs context diffing across turns

Transient infrastructure (timeout/transport) is deliberately UNMAPPED, not
forced into a category: it is retryable weather, not an agent failure.
"""

from __future__ import annotations


# AgentRx nine, kebab-cased. UNMAPPED is the honest tenth bucket.
GOAL_MISINTERPRETATION = "goal-misinterpretation"
WRONG_TOOL = "wrong-tool"
WRONG_ARGUMENT = "wrong-argument"
OBSERVATION_FAILURE = "observation-failure"
CONSTRAINT_VIOLATION = "constraint-violation"
RECOVERY_FAILURE = "recovery-failure"
LOOPING_OVER_ACTION = "looping-over-action"
UNSAFE_TRUST = "unsafe-trust-of-external-content"
STATE_CONTAMINATION = "state-contamination"
UNMAPPED = "unmapped"

_CATEGORIES = (
    GOAL_MISINTERPRETATION, WRONG_TOOL, WRONG_ARGUMENT, OBSERVATION_FAILURE,
    CONSTRAINT_VIOLATION, RECOVERY_FAILURE, LOOPING_OVER_ACTION,
    UNSAFE_TRUST, STATE_CONTAMINATION,
)

# output-text signals, lowercase substring match
_DENIED = ("denied", "not allowed", "outside", "permission", "forbidden")
_NO_SUCH_TOOL = ("command not found", "not recognized", "no such command")
_BAD_TARGET = ("did not match", "not unique", "no such file", "not found",
               "missing", "does not exist")


def _output(rec: dict) -> str:
    return str(rec.get("output") or rec.get("detail") or "")


def classify_record(rec: dict) -> tuple[str, str]:
    """(category | "unmapped", reason) for one journal/tool record."""
    cls = str(rec.get("error_class") or "")
    tool = str(rec.get("tool") or rec.get("name") or "")
    out = _output(rec).lower()
    if cls in ("", "ok"):
        return UNMAPPED, "no-failure"
    if cls == "auth":
        return CONSTRAINT_VIOLATION, "credential/policy constraint"
    if cls == "schema_mismatch":
        return WRONG_ARGUMENT, "argument validation failed"
    if cls == "parse":
        return OBSERVATION_FAILURE, "model output unparseable as tool call"
    if cls in ("timeout", "transport"):
        return UNMAPPED, "transient-infrastructure"
    if cls == "tool-error":
        if any(s in out for s in _DENIED):
            return CONSTRAINT_VIOLATION, "sandbox/approval/permission denial"
        if tool == "shell" and any(s in out for s in _NO_SUCH_TOOL):
            return WRONG_TOOL, "invoked command does not exist"
        if tool in ("write_file", "edit_file") and any(
                s in out for s in _BAD_TARGET):
            return WRONG_ARGUMENT, "bad path or anchor"
    return UNMAPPED, f"uncoded-class:{cls or 'none'}"


def summarize_taxonomy(records: list[dict]) -> dict[str, int]:
    """Category → count over failure records (ok/empty records skipped)."""
    counts: dict[str, int] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("error_class") or "") in ("", "ok"):
            continue
        cat, _ = classify_record(rec)
        counts[cat] = counts.get(cat, 0) + 1
    return counts
