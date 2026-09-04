"""Structured output: inject a JSON Schema into the final-turn prompt and
validate the model's final response, with one schema-error retry.

Used by `exec --output-schema FILE`: when set, the agent loop runs normally;
before the final answer is accepted, its text must extract as JSON that
validates against the schema. On failure, one retry turn is appended with
the validation errors, per the spec ("one auto-retry appending validation
errors").
"""

from __future__ import annotations

import json
import re
from typing import Optional, Tuple

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


class SchemaError(Exception):
    """Cycle-6 config/usage errors around --output-schema (exit 2)."""


def load_schema_file(path) -> dict:
    from pathlib import Path

    p = Path(path).expanduser()
    if not p.exists():
        raise SchemaError(f"--output-schema file not found: {p}")
    try:
        schema = json.loads(p.read_text())
    except json.JSONDecodeError as exc:
        raise SchemaError(f"--output-schema is not valid JSON: {exc}") from exc
    if not isinstance(schema, dict):
        raise SchemaError("--output-schema must be a JSON object (JSON Schema)")
    # Fail fast if jsonschema cannot process it.
    try:
        import jsonschema as _js
    except ImportError:
        raise SchemaError("jsonschema is required for --output-schema") from None
    # R37F3: the handler named a bare `jsonschema` (the module is bound as
    # `_js`) AND a class that does not exist in the package, so an invalid
    # schema raised NameError instead of the SchemaError that maps to exit 2.
    try:
        _js.validators.validator_for(schema).check_schema(schema)
    except _js.exceptions.SchemaError as exc:
        raise SchemaError(f"invalid JSON Schema: {exc}") from exc
    except Exception as exc:  # malformed enough that the validator itself blew up
        raise SchemaError(f"invalid JSON Schema: {exc}") from exc
    return schema


def extract_json(text: str) -> Optional[object]:
    """Extract a JSON value from model output: fenced block first, then the
    largest {...} span, then the whole string."""
    if not text:
        return None
    fence = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    for chunk in fence:
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    candidates = [text.strip()]
    m = _JSON_OBJ_RE.search(text)
    if m:
        candidates.insert(0, m.group(0))
    for chunk in candidates:
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue
    return None


def validate(data: object, schema: dict) -> Tuple[bool, str]:
    """Returns (ok, errors_text)."""
    import jsonschema

    validator = jsonschema.validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if not errors:
        return True, ""
    lines = []
    for e in errors[:10]:
        path = ".".join(str(p) for p in e.path) or "(root)"
        lines.append(f"- {path}: {e.message}")
    return False, "\n".join(lines)


def schema_instructions(schema: dict) -> str:
    return (
        "Your FINAL response must be a single JSON object that validates "
        "against this JSON Schema (no prose outside the JSON):\n"
        f"```json\n{json.dumps(schema, indent=2)}\n```\n"
        "Respond with ONLY the JSON object."
    )


def retry_prompt(errors: str) -> str:
    return (
        "Your previous response failed JSON Schema validation. Fix it and "
        "respond with ONLY the corrected JSON object.\nValidation errors:\n"
        f"{errors}"
    )
