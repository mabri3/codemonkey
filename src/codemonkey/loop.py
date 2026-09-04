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

import time

from typing import Callable, Optional

from . import protocol as prompt_protocol
from . import tools as tool_registry
from .providers.base import ChatTurn, ProviderBase, ProviderError
from .retry import TOOLS_RE as _TOOLS_RE
from .sandbox import ToolContext


class FallbackRecorded:
    """In-memory per-provider prompt-protocol fallback record (auto mode)."""

    def __init__(self) -> None:
        self.force_prompt_providers: set[int] = set()

    def remember(self, provider: ProviderBase) -> None:
        self.force_prompt_providers.add(id(provider))

    def must_prompt(self, provider: ProviderBase) -> bool:
        return id(provider) in self.force_prompt_providers


# loop7 cycle 32: tools whose retry could double side effects; replay from the
# journal instead of re-executing when an outcome is already recorded.
_MUTATING_TOOLS = {"write_file", "edit_file"}


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
    approval: Optional[str] = None,
    approval_notice_stream=None,
    context_limit: Optional[int] = None,
    compaction=None,
    max_edit_retries: int = 1,
    observation_budget: int = 24000,
    verify_command: Optional[str] = None,
    max_verify_retries: int = 1,
    memory_enabled: bool = True,
    prompt_cache: bool = True,
    journal_thread: str = "",
    journal_run: str = "",
    perm_rules: list | None = None,
) -> ChatTurn:
    """Drive the model until a final text answer or max_turns.

    `approval` (None disables the gate) is a policy name;
    `approval_notice_stream` overrides where soft-deny notices go (default:
    sys.stderr resolved at call time).

    on_event receives dicts: {type: turn.started}, {type: tool.started, name},
    {type: tool.completed, name, ok}, {type: turn.completed, usage},
    {type: error, message}. Returns the final ChatTurn, whose
    ``all_messages`` attribute is the full conversation (history + this run).
    """
    fallback = fallback or FallbackRecorded()
    specs = tool_registry.SPECS
    system = prompt_protocol.prompt_block(specs, memory_enabled=memory_enabled)
    if system_extra:
        system = system_extra + "\n\n" + system

    mode = tool_protocol if tool_protocol in ("native", "prompt") else "auto"
    edit_retries_left = max(0, int(max_edit_retries))
    obs_spent = 0
    verify_retries_left = max(0, int(max_verify_retries))
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

        # ---- auto-compaction (loop2, cycle 15) --------------------------
        # Estimate the message stack against the context budget before every
        # provider call; when over budget, run the registry-selected
        # compaction strategy and re-inject the system prompt (anti
        # "governance decay": post-compaction turns ALWAYS carry the system).
        if compaction is not None and context_limit and len(messages) > 1:
            from .strategies.compaction import _estimate_tokens

            if _estimate_tokens(messages) > int(context_limit):
                try:
                    compacted = compaction.maybe_compact(
                        messages, budget_tokens=context_limit,
                        provider=provider,
                    )
                except Exception:
                    compacted = None
                if compacted and len(compacted) < len(messages):
                    n_dropped = len(messages) - len(compacted)
                    kept = list(compacted)
                    # Dedupe multiple briefs; guarantee at least one
                    # "[prior context]" marker (anti governance-decay: the
                    # model must KNOW earlier context was condensed).
                    briefs = [
                        m for m in kept
                        if m.get("role") == "system" and str(m.get("content", "")).startswith("[prior context]")
                    ]
                    if briefs:
                        first_brief = briefs[0]
                        kept = [
                            m for m in kept
                            if not (m.get("role") == "system" and str(m.get("content", "")).startswith("[prior context]"))
                        ]
                        kept.insert(0, first_brief)
                    else:
                        kept.insert(0, {
                            "role": "system",
                            "content": "[prior context] Earlier conversation was condensed by policy; the system prompt still fully applies.",
                        })
                    messages = kept
                    if on_event:
                        on_event({
                            "type": "notice",
                            "message": f"auto-compaction dropped {n_dropped} message(s) to fit the context budget",
                        })

        try:
            if use_prompt:
                turn = provider.chat(
                    messages, system=system, stream=stream, on_token=on_token,
                    cache_prompt=prompt_cache,
                )
            elif native_first:
                turn = provider.chat(
                    messages,
                    system=system,
                    stream=stream,
                    tools=_native_specs(specs, provider),
                    on_token=on_token,
                    cache_prompt=prompt_cache,
                )
            else:
                turn = provider.chat(
                    messages, system=system, stream=stream, on_token=on_token,
                    cache_prompt=prompt_cache,
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
                        messages, system=system, stream=stream, on_token=on_token,
                        cache_prompt=prompt_cache,
                    )
                except ProviderError as exc2:
                    if on_event:
                        on_event({"type": "error", "message": str(exc2)})
                        exc2.reported = True
                    raise
            else:
                if on_event:
                    on_event({"type": "error", "message": str(exc)})
                    exc.reported = True
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

        # loop3 bridge: native call returned TEXT that still looks like prompt-
        # protocol output (some models wrap tool calls in text even when native
        # tools are accepted — kimi/3459 emits TOOL_CALL + special tokens). Parse
        # the prompt protocol from the content so those calls aren't lost.
        calls = calls or []
        if (not calls and not use_prompt and turn.content
                and "TOOL_CALL:" in (turn.content or "")):
            p_calls, _p_prose = prompt_protocol.parse_tool_calls(turn.content)
            if p_calls and not any(c.get("error") for c in p_calls):
                calls = p_calls
                if on_event:
                    on_event({"type": "notice",
                              "message": "native turn carried prompt-protocol tool call(s); parsing them"})

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
                            retry = provider.chat(
                                messages, system=system, stream=stream,
                                on_token=on_token, cache_prompt=prompt_cache,
                            )
                        elif native_first:
                            retry = provider.chat(
                                messages, system=system, stream=stream,
                                tools=_native_specs(specs, provider), on_token=on_token,
                                cache_prompt=prompt_cache,
                            )
                        else:
                            retry = provider.chat(
                                messages, system=system, stream=stream,
                                on_token=on_token, cache_prompt=prompt_cache,
                            )
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

        # ---- parallel tool execution (loop2, cycle 12) --------------------
        # All calls in this turn are gathered first; independent calls run
        # concurrently in a thread pool; results are re-ordered to call order
        # so the transcript is deterministic. Errors (parse/approval/exec)
        # are isolated per call: one failure never kills its siblings.
        def _run_one(idx: int, call: dict):
            """Execute one parsed call. Returns (idx, name, ok, output, meta)."""
            name = call.get("name", "")
            if on_event:
                # 51F5: the text renderer prints `$ {item.command}` and
                # `[exit {item.exit_code}]`, but nothing ever populated those
                # keys, so every tool trace read `$ ` / `[exit None]` no matter
                # what ran. Carry the args here and the output below so the
                # trace shows the real command — the blank trace is what made
                # the empty-schema tool failure so hard to diagnose.
                on_event({"type": "tool.started", "name": name,
                          "args": call.get("args") or {}})
            if call.get("error"):
                return (idx, name, False, f"error: {call['error']}", None)
            # loop9 cycle 36: rule-based permissions BEFORE the approval gate.
            rule_decision = None
            try:
                from .permissions import evaluate as _pe

                rule_decision = _pe(perm_rules or [], name, call.get("args") or {})
                if rule_decision and journal_thread:
                    try:
                        from .journal import record as _jr

                        _jr(journal_thread, "outcome", tool=name, key=jkey + ":rule",
                            status=f"rule-{rule_decision}")
                    except OSError:
                        pass
            except ValueError as _ve:
                if on_event:
                    on_event({"type": "error", "message": f"permissions config: {_ve}"})
                return (idx, name, False, f"error: permissions config invalid: {_ve}",
                        {"raised": True})
            if rule_decision == "deny":
                if on_event:
                    on_event({"type": "notice",
                              "message": f"permission rule: {name} denied by rule"})
                return (idx, name, False,
                        "error: denied by permission rule", {"rule": "deny"})

            # loop20 cycle 57: tool-argument validation gate. Structured
            # mismatch goes back through the self-heal loop instead of dying
            # on a KeyError inside the tool.
            try:
                from .argvalidate import validate_args as _va

                _bad = _va(name, call.get("args") or {})
                if _bad is not None:
                    if journal_thread:
                        try:
                            from .journal import args_key as _akv, record as _jr

                            _jr(journal_thread, "outcome", tool=name,
                                key=_akv(journal_thread, _turn_no, idx,
                                         call.get("args") or {},
                                         run=journal_run),
                                status="error", error_class="schema_mismatch",
                                output=_bad["detail"])
                        except OSError:
                            pass
                    return (idx, name, False,
                            f"error: {_bad['detail']}", {"error_class": "schema_mismatch"})
            except OSError:
                pass

            # Approval gate (cycle 8): evaluate policy BEFORE dispatch.
            # (rule_decision == 'ask' forces the gate on; 'allow' skips it)
            if approval and rule_decision != "allow":
                from . import approvals as approvals_mod

                decision = approvals_mod.decide(name, approval, sandbox=ctx.sandbox)
                if decision.action == approvals_mod.SOFT_DENY:
                    approvals_mod.notice_to_stderr(decision, approval_notice_stream)
                    if on_event:
                        on_event({
                            "type": "tool.completed",
                            "name": name,
                            "ok": False,
                            "approval": "soft-deny",
                        })
                    return (idx, name, False,
                            approvals_mod.tool_result_notice(name, decision),
                            {"approval": "soft-deny"})
            # loop7 cycle 31/32: journal intent + idempotent replay
            jkey = ""
            if journal_thread:
                try:
                    from .journal import args_key as _ak, find_outcome as _fo, record as _jr

                    jkey = _ak(journal_thread, _turn_no, idx, call.get("args") or {},
                               run=journal_run)
                    hit = _fo(journal_thread, jkey) if name in _MUTATING_TOOLS else None
                    if hit is not None:
                        _jr(journal_thread, "outcome", tool=name, key=jkey,
                            status="replayed",
                            output=hit.get("output", ""))
                        if on_event:
                            on_event({"type": "notice",
                                      "message": f"idempotent replay: {name} ({jkey})"})
                        return (idx, name, hit.get("status") == "ok",
                                hit.get("output", ""),
                                {"replayed": True, "_jkey": jkey})
                    _jr(journal_thread, "intent", tool=name, key=jkey)
                except OSError:
                    jkey = ""
            t0 = time.monotonic()
            try:
                result = tool_registry.dispatch(name, call.get("args") or {}, ctx)
            except Exception as exc:  # isolation: sibling calls must survive
                if journal_thread and jkey:
                    try:
                        from .journal import classify_error as _ce, record as _jr

                        _jr(journal_thread, "outcome", tool=name, key=jkey,
                            status="error", error_class=_ce(exc),
                            duration_ms=int((time.monotonic() - t0) * 1000))
                    except OSError:
                        pass
                return (idx, name, False, f"error: {exc}",
                        {"raised": True, "_jkey": jkey})
            if journal_thread and jkey:
                try:
                    from .journal import record as _jr

                    _jr(journal_thread, "outcome", tool=name, key=jkey,
                        status=("ok" if result.ok else "error"),
                        error_class=("tool-error" if not result.ok else ""),
                        duration_ms=int((time.monotonic() - t0) * 1000),
                        output=result.output,
                        )
                except OSError:
                    pass
            return (idx, name, result.ok, result.output, {"_jkey": jkey})

        max_workers = min(len(calls), 8) if len(calls) > 1 else 1
        if max_workers > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                outcomes = list(pool.map(lambda pair: _run_one(*pair),
                                         list(enumerate(calls))))
        else:
            outcomes = [_run_one(0, calls[0])] if calls else []

        outcomes.sort(key=lambda o: o[0])  # deterministic call order
        edit_retry_hint = None
        for idx, name, ok, result_output, meta in outcomes:
            # 35F1: `_jkey` is the journal key carried back from _run_one (it
            # is a LOCAL there — the old code read an unbound `jkey` in this
            # scope and the surrounding `except Exception` swallowed the
            # NameError, so the cycle-35 slim stat was never recorded).
            meta = dict(meta or {})
            jkey = meta.pop("_jkey", "")
            if on_event:
                ev = {"type": "tool.completed", "name": name, "ok": ok,
                      "output": (result_output or "")[:2000]}
                if meta:
                    ev.update(meta)
                on_event(ev)
            # ---- observation budget (loop3, cycle 17) --------------------
            # Keep the PARTIAL signal pattern: useful prefix + structurally
            # distinct marker + continuation hint. Ledger shared across the
            # whole run so 3 fat outputs can't silently evict the task.
            # loop8 cycle 35: deterministic slimming before budget/spill
            try:
                from .slim import slim as _slim

                result_output, _slim_stats = _slim(result_output)
                if journal_thread and jkey and _slim_stats.get("applied"):
                    try:
                        from .journal import record as _jr

                        _jr(journal_thread, "outcome", tool=name, key=jkey + ":slim",
                            status="slimmed",
                            output=str(_slim_stats.get("chars_saved", 0)))
                    except OSError:
                        pass
            except Exception:
                pass
            if observation_budget > 0 and len(result_output) > observation_budget - obs_spent:
                # loop6 cycle 30: spill the full output verbatim and point the
                # model at it, instead of only eliding (which caused re-runs).
                try:
                    from .spill import truncate_with_spill

                    result_output = truncate_with_spill(
                        result_output, max(200, observation_budget - obs_spent),
                        tool=name,
                    )
                except OSError:
                    # spill unavailable (disk/home unwritable): fall back to the
                    # cycle-17 pure-truncation behavior
                    allowance = max(0, observation_budget - obs_spent)
                    elided = len(result_output) - allowance
                    result_output = (
                        result_output[:allowance]
                        + f"\n\n[PARTIAL: {elided} chars elided by the observation budget "
                        f"({observation_budget} per run) — rerun the tool with narrower args]"
                    )
                obs_spent = observation_budget
                if on_event:
                    on_event({"type": "notice",
                              "message": f"observation budget: {name} output truncated (spilled where noted)"})
            else:
                obs_spent += len(result_output)
            messages.append(
                {
                    "role": "user",
                    "content": f"TOOL_RESULT {name}:\n{result_output}",
                }
            )
            # ---- self-heal edit retries (loop3, cycle 16) ----------------
            # edit_file failure with a structured error (near-miss anchors /
            # match counts) is actionable: schedule ONE corrective re-prompt.
            if (not ok and name == "edit_file"
                    and edit_retries_left > 0
                    and result_output.startswith("error:")):
                edit_retry_hint = (
                    "Your edit_file call failed with:\n"
                    f"{result_output}\n"
                    "Retry ONCE with a corrected SEARCH block: copy the exact "
                    "current file text for SEARCH (re-read the file with "
                    "read_file if unsure). If it still fails, report and stop."
                )
        if edit_retry_hint is not None:
            edit_retries_left -= 1
            messages.append({"role": "user", "content": edit_retry_hint})
            if on_event:
                on_event({"type": "notice",
                          "message": "self-heal: edit failed — retrying with error feedback"})
            continue

        # ---- verify gate (loop4, cycle 19) ------------------------------
        # After any turn whose MUTATING tool calls succeeded, run the
        # configured verify command under the sandbox; on failure, feed the
        # trimmed output back for a bounded corrective turn.
        if (verify_command and verify_retries_left > 0
                and any(name in ("write_file", "edit_file", "shell") and ok
                        for _i, name, ok, _o, _m in outcomes)):
            if on_event:
                on_event({"type": "verify.started", "command": verify_command})
            import subprocess as _sp

            try:
                vr = _sp.run(
                    verify_command, shell=True, cwd=str(ctx.workdir),
                    capture_output=True, text=True,
                    timeout=max(5, int(ctx.timeout or 30)),
                )
                v_code = vr.returncode
                v_ok = v_code == 0
                v_text = (vr.stdout or "") + (("\n" + vr.stderr) if vr.stderr else "")
            except _sp.TimeoutExpired as exc:
                v_ok = False
                # 124 is the conventional timeout status (GNU coreutils
                # `timeout`); it is a real signal, not a fabricated 0/1.
                v_code = 124
                v_text = f"verify command timed out after {exc.timeout}s"
            if len(v_text) > 4000:
                v_text = v_text[:4000] + "\n[verify output trimmed]"
            if on_event:
                on_event({"type": "verify.completed",
                          "ok": v_ok, "exit_code": v_code})
            obs_spent += len(v_text)
            if not v_ok:
                verify_retries_left -= 1
                messages.append({
                    "role": "user",
                    "content": ("VERIFY FAILED (exit != 0). Output:\n" + v_text
                                + "\nFix the code so the verify command passes, "
                                "then briefly confirm."),
                })
                if on_event:
                    on_event({"type": "notice",
                              "message": "verify gate: failed — corrective turn granted"})
                continue
        last_turn = turn

    # max_turns bail
    if on_event:
        on_event({"type": "error",
                  "message": f"max_turns ({max_turns}) reached without a final answer"})
    last_turn.all_messages = messages
    return last_turn


def _native_specs(specs: dict, provider=None) -> list[dict]:
    """Native tool array in the wire shape this provider's protocol expects."""
    from .native import tool_specs_for

    return tool_specs_for(getattr(provider, "protocol", "openai"), specs)