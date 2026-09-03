"""Native tool protocol.

Feeds provider-native tool calls (OpenAI `tools` / Anthropic `tool_use`) and
returns results as proper tool-role messages. When the server rejects the
`tools` parameter (llama.cpp answers HTTP 500), `resolved_policy` — via the
loop — falls back to the prompt protocol and remembers it for the provider.
"""

from __future__ import annotations

from .protocol import MARKER

# Wire-schema fragments the loop uses to build request payloads.


_EMPTY_SCHEMA = {"type": "object", "properties": {}}


def _schema_for(name: str, params: dict | None) -> dict:
    """Wire schema for one tool, falling back to the registry then to empty.

    51F1: an empty `properties` map is a positive claim that the tool takes no
    arguments. A model that honours the declared schema then sends `{}` and
    every tool dies on a missing key, so the real schema must reach the wire.
    """
    if params is not None and name in params:
        return params[name]
    from .tools import PARAMS

    return PARAMS.get(name, _EMPTY_SCHEMA)


def openai_tool_specs(specs: dict, params: dict | None = None) -> list[dict]:
    """{name: one_line_spec} -> OpenAI `tools` array (function type)."""
    tools = []
    for name, spec in specs.items():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec,
                    "parameters": _schema_for(name, params),
                },
            }
        )
    return tools


def anthropic_tool_specs(specs: dict, params: dict | None = None) -> list[dict]:
    """{name: one_line_spec} -> Anthropic `tools` array (input_schema shape).

    The Anthropic Messages API takes a flat {name, description, input_schema}
    entry, not OpenAI's nested {"type": "function", "function": {...}}. Sending
    the OpenAI shape to an anthropic-protocol provider is rejected outright.
    """
    return [
        {
            "name": name,
            "description": spec,
            "input_schema": _schema_for(name, params),
        }
        for name, spec in specs.items()
    ]


def tool_specs_for(protocol: str, specs: dict, params: dict | None = None) -> list[dict]:
    """Native tool array in whichever wire shape `protocol` expects."""
    if (protocol or "openai").lower() == "anthropic":
        return anthropic_tool_specs(specs, params)
    return openai_tool_specs(specs, params)


def openai_tool_result_message(call: dict, output: str) -> dict:
    """Assistant-visible tool result for the prompt-protocol transcript."""
    return {
        "role": "user",
        "content": f"TOOL_RESULT {call.get('name', '?')}: {output}",
    }
