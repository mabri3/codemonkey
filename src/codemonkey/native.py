"""Native tool protocol.

Feeds provider-native tool calls (OpenAI `tools` / Anthropic `tool_use`) and
returns results as proper tool-role messages. When the server rejects the
`tools` parameter (llama.cpp answers HTTP 500), `resolved_policy` — via the
loop — falls back to the prompt protocol and remembers it for the provider.
"""

from __future__ import annotations

from .protocol import MARKER

# Wire-schema fragments the loop uses to build request payloads.


def openai_tool_specs(specs: dict) -> list[dict]:
    """{name: one_line_spec} -> OpenAI `tools` array (function type)."""
    tools = []
    for name, spec in specs.items():
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec,
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        )
    return tools


def openai_tool_result_message(call: dict, output: str) -> dict:
    """Assistant-visible tool result for the prompt-protocol transcript."""
    return {
        "role": "user",
        "content": f"TOOL_RESULT {call.get('name', '?')}: {output}",
    }
