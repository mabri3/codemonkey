"""Agent loop: model -> tool calls -> execute under policy -> feed results.

`tool_protocol` (config, per provider):
  native : provider-native tool calls only; a NetworkToolError escalates.
  prompt : prompt protocol only (`TOOL_CALL:` text blocks).
  auto   : try native first for openai-protocol providers; if the server
           rejects the `tools` parameter (HTTP 500 — verified for the local
           llama.cpp build), retry the SAME turn with the prompt protocol and
           remember the fallback for the provider (attribute, in-process).
           That fallback is acceptance ground truth (A9) — it is a feature,
           not a bug.
"""

from __future__ import annotations

import re
from typing import Callable, Optional

from . import protocol as prompt_protocol
from . import tools as tool_registry
from .providers.base import ChatTurn, ProviderBase, ProviderError
from .sandbox import ToolContext

_TOOLS_RE = re.compile(r"(?i)tools")


class FallbackRecorded:
    """In-memory per-provider prompt-protocol fallback record (auto mode)."""

    def __init__(self) -> None:
        self.force_prompt_providers: set[int] = set()

    def remember(self, provider: ProviderBase) -> None:
        self.force_prompt_providers.add(id(provider))

    def must_prompt(self, provider: ProviderBase) -> bool:
        return id(provider) in self.force_prompt_providers


def looks_like_tools_rejection(exc: ProviderError) -> bool:
    return exc.status is not None and exc.status >= 400 and bool(
        _TOOLS_RE.search(str(exc))
    )


def run_turns(
    provider: ProviderBase,
    user_prompt: str,
    ctx: ToolContext,
    *,
    history: Optional[list] = None,
    tool_protocol: str = "auto",
    system_extra: str = "",
    max_turns: int = 30,
    stream: bool = False,
    on_event: Optional[Callable[[dict], None]] = None,
    on_token: Optional[Callable[[str], None]] = None,
    fallback: Optional[FallbackRecorded] = None,
    schema: Optional[dict] = None,
) -> ChatTurn:
    """Drive the model until a final text answer or max_turns.

    on_event receives dicts: {type: turn.started}, {type: tool.started, name},
    {type: tool.completed, name, ok}, {type: turn.completed, usage},
    {type: error, message}. Returns the final ChatTurn, whose
    ``all_messages`` attribute is the full conversation (history + this run).
    """
    fallback = fallback or FallbackRecorded()
    specs = tool_registry.SPECS
    system = prompt_protocol.prompt_block(specs)
    if system_extra:
        system = system_extra + "\n\n" + system

    mode = tool_protocol if tool_protocol in ("native", "prompt") else "auto"
    messages: list[dict] = list(history or [])
    if user_prompt:
        messages.append({"role": "user", "content": user_prompt})
    pre_run_len = len(messages)
    last_turn = ChatTurn()

    for _turn_no in range(1, max_turns + 1):
        if on_event:
            on_event({"type": "turn.started"})

        use_prompt = mode == "prompt" or (
            mode == "auto" and fallback.must_prompt(provider)
        )
        native_first = mode == "native" or (
            mode == "auto" and not use_prompt and provider.protocol == "openai"
        )

        try:
            if use_prompt:
                turn = provider.chat(
                    messages, system=system, stream=stream, on_token=on_token
                )
            elif native_first:
                turn = provider.chat(
                    messages,
                    system=system,
                    stream=stream,
                    tools=_native_specs(specs),
                    on_token=on_token,
                )
            else:
                turn = provider.chat(
                    messages, system=system, stream=stream, on_token=on_token
                )
        except ProviderError as exc:
            if mode == "auto" and native_first and looks_like_tools_rejection(exc):
                # The llama.cpp tools-parameter 500 (A9): switch to prompt
                # protocol for this provider and retry the same turn.
                fallback.remember(provider)
                if on_event:
                    on_event({"type": "notice",
                              "message": "tools parameter rejected; using prompt protocol"})
                try:
                    turn = provider.chat(
                        messages, system=system, stream=stream, on_token=on_token
                    )
                except ProviderError as exc2:
                    if on_event:
                        on_event({"type": "error", "message": str(exc2)})
                    raise
            else:
                if on_event:
                    on_event({"type": "error", "message": str(exc)})
                raise

        if not use_prompt:
            calls = [
                {"name": c["name"], "args": c.get("args", {})}
                for c in turn.tool_calls
            ]
        else:
            calls, _prose = prompt_protocol.parse_tool_calls(turn.content)

        if on_event:
            on_event({"type": "turn.completed", "usage": turn.usage})

        if not calls:
            last_turn = turn
            # Cycle 6: structured-output schema validation with one retry.
            if schema is not None:
                from . import schema as schema_mod

                extracted = schema_mod.extract_json(turn.content or "")
                ok = False
                errors_text = ""
                if extracted is not None:
                    ok, errors_text = schema_mod.validate(extracted, schema)
                    if not ok:
                        errors_text = "extracted JSON failed validation:\n" + errors_text
                else:
                    errors_text = "- (root): response did not contain a JSON object"
                if not ok:
                    if on_event:
                        on_event({
                            "type": "notice",
                            "message": "schema validation failed; retrying once",
                        })
                    messages.append({"role": "assistant", "content": turn.content or ""})
                    messages.append({"role": "user", "content": schema_mod.retry_prompt(errors_text)})
                    # 6F2: the retry is its OWN turn — wrap provider call with
                    # turn markers so turn.started/turn.completed stay 1:1.
                    if on_event:
                        on_event({"type": "turn.started"})
                    try:
                        if use_prompt:
                            retry = provider.chat(messages, system=system, stream=stream, on_token=on_token)
                        elif native_first:
                            retry = provider.chat(
                                messages, system=system, stream=stream,
                                tools=_native_specs(specs), on_token=on_token,
                            )
                        else:
                            retry = provider.chat(messages, system=system, stream=stream, on_token=on_token)
                    except ProviderError:
                        retry = None
                        if on_event:
                            on_event({"type": "error", "message": "schema retry: provider error"})
                    if retry is not None:
                        if on_event:
                            on_event({"type": "turn.completed", "usage": retry.usage})
                        messages.append({"role": "assistant", "content": retry.content or ""})
                        extracted2 = schema_mod.extract_json(retry.content or "")
                        ok2 = False
                        errors2 = ""
                        if extracted2 is not None:
                            ok2, errors2 = schema_mod.validate(extracted2, schema)
                        else:
                            errors2 = "- (root): retry response did not contain a JSON object"
                        if ok2:
                            last_turn = retry
                            if on_event:
                                on_event({"type": "notice", "message": "schema validation passed on retry"})
                        else:
                            if on_event:
                                on_event({
                                    "type": "error",
                                    "message": "schema validation failed after retry: " + errors2,
                                })
                    # 6F2: strip the retry scaffolding from the tail of the
                    # same messages list before it is persisted — resumed
                    # threads must not replay the injected schema turn or the
                    # retry meta-dialogue.
                    #   error path: drop the bad assistant answer + retry
                    #     prompt (the final-answer emissions still write the
                    #     initial answer as the closing message);
                    #   success path: additionally swap the good retry answer
                    #     into the bad-answer slot so the store keeps exactly
                    #     [pristine user prompt, final answer].
                    if on_event:
                        drop_tail = 3 if retry is not None else 2
                        on_event({
                            "type": "persist.drop",
                            "messages": messages,
                            "meta": {"pre_run_len": pre_run_len,
                                     "drop_tail": drop_tail,
                                     "replace_with": (
                                         retry.content if retry is not None else None
                                     )},
                        })
            last_turn.all_messages = messages
            return last_turn

        messages.append({"role": "assistant", "content": turn.content or ""})
        for call in calls:
            name = call.get("name", "")
            if on_event:
                on_event({"type": "tool.started", "name": name})
            if call.get("error"):
                result_output = f"error: {call['error']}"
                ok = False
            else:
                result = tool_registry.dispatch(name, call.get("args") or {}, ctx)
                result_output = result.output
                ok = result.ok
            if on_event:
                on_event({"type": "tool.completed", "name": name, "ok": ok})
            messages.append(
                {
                    "role": "user",
                    "content": f"TOOL_RESULT {name}:\n{result_output}",
                }
            )
        last_turn = turn

    # max_turns bail
    if on_event:
        on_event({"type": "error",
                  "message": f"max_turns ({max_turns}) reached without a final answer"})
    last_turn.all_messages = messages
    return last_turn


def _native_specs(specs: dict) -> list[dict]:
    from .native import openai_tool_specs

    return openai_tool_specs(specs)
