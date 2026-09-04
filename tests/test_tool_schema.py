"""Native tool-protocol wire schemas (cycle 50).

Regression cover for 51F1: openai_tool_specs used to emit
`{"type": "object", "properties": {}}` for every tool, which tells the model
the tools take NO arguments. Schema-following models answered `{}` and every
call died on a missing key (shell's args["command"] -> `error: 'command'`),
so the whole tool loop was dead against such a model.
"""

from __future__ import annotations

import inspect

import pytest

from codemonkey import native
from codemonkey.tools import PARAMS, SPECS, _MODULES


def test_every_tool_has_a_schema():
    assert set(PARAMS) == set(SPECS) == set(_MODULES)


def test_no_tool_is_advertised_as_argument_free():
    """The exact 51F1 defect: a tool that takes args advertising none."""
    for name, schema in PARAMS.items():
        assert schema.get("type") == "object", name
        assert schema.get("properties"), f"{name} advertises no arguments"


@pytest.mark.parametrize(
    "name,required",
    [
        ("shell", "command"),
        ("read_file", "path"),
        ("write_file", "path"),
        ("glob", "pattern"),
        ("search", "pattern"),
        ("web_fetch", "url"),
        ("update_memory", "fact"),
        ("delegate", "task"),
        ("delegate_batch", "tasks"),
    ],
)
def test_required_arguments_are_declared(name, required):
    schema = PARAMS[name]
    assert required in schema["properties"], f"{name}.{required} missing"
    assert required in schema.get("required", []), f"{name}.{required} not required"


def test_declared_properties_match_what_the_tool_reads():
    """Guard against schema drift: every declared arg is named in the source."""
    for name, schema in PARAMS.items():
        # cycle 74: multi-tool modules register shim classes exposing .run —
        # grade the code that actually reads the args (the run function).
        src = inspect.getsource(_MODULES[name].run)
        for prop in schema["properties"]:
            assert f'"{prop}"' in src or f"'{prop}'" in src, f"{name}.{prop} unused"


def test_openai_shape_carries_the_real_parameters():
    tools = native.openai_tool_specs(SPECS)
    shell = next(t for t in tools if t["function"]["name"] == "shell")
    params = shell["function"]["parameters"]
    assert params["properties"]["command"]["type"] == "string"
    assert params["required"] == ["command"]


def test_anthropic_shape_is_flat_with_input_schema():
    tools = native.anthropic_tool_specs(SPECS)
    shell = next(t for t in tools if t["name"] == "shell")
    # Anthropic takes {name, description, input_schema} — NOT the OpenAI
    # {"type": "function", "function": {...}} nesting.
    assert set(shell) == {"name", "description", "input_schema"}
    assert shell["input_schema"]["required"] == ["command"]


def test_tool_specs_for_dispatches_on_protocol():
    assert "function" in native.tool_specs_for("openai", SPECS)[0]
    assert "input_schema" in native.tool_specs_for("anthropic", SPECS)[0]
    # unknown protocol falls back to the OpenAI shape
    assert "function" in native.tool_specs_for("weird", SPECS)[0]
