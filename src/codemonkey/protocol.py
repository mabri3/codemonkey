"""Prompt tool protocol: `TOOL_CALL: {"name": ..., "arguments": {...}}` in text.

The local llama.cpp server cannot accept the OpenAI `tools` parameter, so the
model emits tool calls as plain text. The system prompt advertises the tool
set (from `tools.SPECS`); this module parses calls back out of the response.

Parser tolerance (verified by tests): fenced ```json/code blocks, multiple
calls in one response, malformed JSON entries (reported as error entries, not
exceptions), a marker line followed by a fenced body, and stray prose.
"""

from __future__ import annotations

import json

MARKER = "TOOL_CALL:"


def prompt_block(specs: dict, *, memory_enabled: bool = True) -> str:
    """Build the tool-advertising block for the system prompt.

    `specs` is the {name: one_line_spec} map from the tool registry.
    `memory_enabled=False` hides update_memory entirely (strategies.memory=none):
    the tool stays registered (calls soft-error honestly) but is not advertised.
    """
    if not memory_enabled:
        specs = {k: v for k, v in specs.items() if k != "update_memory"}
    lines = [
        "You have tools. To call one, output a line starting with TOOL_CALL: "
        "followed by a single JSON object on the SAME line:",
        'TOOL_CALL: {"name": "<tool>", "arguments": { ... }}',
        "You may wrap calls in a code fence. You may make several calls, one "
        "TOOL_CALL: line each. After the tool results are returned to you as "
        "user messages, either call more tools or give your final answer.",
        "",
        "Available tools:",
    ]
    for name, spec in specs.items():
        lines.append(f"  - {spec}")
    return "\n".join(lines)


def parse_tool_calls(text: str) -> tuple:
    """Parse `text` into (calls, prose).

    calls: list of {"name", "args", "error"?} dicts, in order of appearance.
    prose: the response with tool-call lines/fences stripped.
    """
    calls: list[dict] = []
    prose_lines: list[str] = []
    in_fence = False
    fence_lines: list[str] = []
    fence_is_call = False  # fence directly opened by a bare marker line
    expect_call_body = False  # bare marker line; JSON comes next

    for line in text.splitlines():
        stripped = line.strip()

        if in_fence:
            if stripped.startswith("```"):
                if fence_is_call:
                    body = "\n".join(fence_lines).strip()
                    calls.append(_parse_one(body) if body else _missing_call())
                else:
                    calls.extend(_parse_lines(fence_lines))
                fence_lines = []
                in_fence = False
                fence_is_call = False
            else:
                fence_lines.append(line)
            continue

        if stripped.startswith("```"):
            in_fence = True
            fence_lines = []
            fence_is_call = expect_call_body
            expect_call_body = False
            continue

        if stripped.startswith(MARKER):
            expect_call_body = False
            rest = stripped[len(MARKER):].strip()
            if rest:
                calls.append(_parse_one(rest))
            else:
                expect_call_body = True  # JSON on following line / fence
            continue

        if expect_call_body:
            expect_call_body = False
            if stripped:
                calls.append(_parse_one(stripped))
                continue
            calls.append(_missing_call())
            continue

        prose_lines.append(line)

    if in_fence and fence_lines:
        # unterminated fence — best effort over what we saw
        calls.extend(_parse_lines(fence_lines))
    prose = "\n".join(prose_lines).strip()
    return calls, prose


def _missing_call() -> dict:
    return {"name": "", "args": {}, "error": "TOOL_CALL with no JSON body"}


def _parse_lines(lines: list) -> list:
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(MARKER):
            rest = stripped[len(MARKER):].strip()
            out.append(_parse_one(rest) if rest else _missing_call())
        elif stripped.startswith("{"):
            # bare JSON inside a fence: a call only if it names a tool
            obj = _parse_one(stripped)
            if obj.get("name") or obj.get("error"):
                out.append(obj)
    return out


def _extract_json_object(text: str) -> Optional[str]:
    """Return the first balanced top-level JSON object in `text`, or "".

    models append special tokens / prose after the JSON (observed live:
    `TOOL_CALL: {...} <|tool_call_end|> <|tool_calls_section_end|>` from
    kimi-k2.7 via 3459), so a strict whole-blob json.loads is too brittle.
    Scan for the first '{' and walk braces respecting strings/escapes.
    """
    depth = 0
    in_str = False
    esc = False
    start = -1
    for i, ch in enumerate(text):
        if start < 0:
            if ch == "{":
                start = i
                depth = 1
            continue
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return ""


def _parse_one(blob: str) -> dict:
    blob = blob.strip()
    # Tolerate trailing junk after the JSON object (special tokens, prose):
    # first try the strict whole-blob parse; on failure extract the first
    # balanced {...} and retry with that.
    try:
        obj = json.loads(blob)
    except json.JSONDecodeError:
        candidate = _extract_json_object(blob)
        if not candidate:
            return {"name": "", "args": {}, "error": f"malformed tool-call JSON: no JSON object found in: {blob[:80]!r}"}
        blob = candidate
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError as exc:
            return {"name": "", "args": {}, "error": f"malformed tool-call JSON: {exc}"}
    except json.JSONDecodeError as exc:
        return {"name": "", "args": {}, "error": f"malformed tool-call JSON: {exc}"}
    if not isinstance(obj, dict):
        return {"name": "", "args": {}, "error": "tool call must be a JSON object"}
    args = obj.get("arguments", obj.get("args", obj.get("input", {})))
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"_raw": args}
    if not isinstance(args, dict):
        args = {"_raw": args}
    return {"name": str(obj.get("name", "")), "args": args}
