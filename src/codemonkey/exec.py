"""Non-interactive `exec` mode — scriptable by other agents and CI.

Contract (build/spec.md):
- stdout purity      text mode: ONLY the final response on stdout
                     --json mode: ONLY JSONL events on stdout
                     everything else (deltas, tool echoes, notices) → stderr
- stdin              `-` = stdin IS the prompt; piped stdin + prompt arg =
                     piped content prepended as context
- git guard          cwd must be inside a git repo → else exit 2 naming
                     `--skip-git-repo-check`
- exit codes         0 success · 1 run error · 2 usage/auth error
- events             thread.started{thread_id} → turn.* / thread.item.* →
                     turn.completed{usage} (see events.py)
"""

from __future__ import annotations

import json
import os
import sys
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from . import events


def _read_schema(schema_path: Optional[Path]) -> Optional[dict]:
    if schema_path is None:
        return None
    from . import schema as schema_mod

    return schema_mod.load_schema_file(schema_path)


class ExecUsageError(Exception):
    """Exit-2 (usage/auth) errors."""


def find_git_root(cwd: Path) -> Optional[Path]:
    p = Path(cwd).resolve()
    for cand in (p, *p.parents):
        if (cand / ".git").exists():
            return cand
    return None


def _schema_turn_check(turn, schema: Optional[dict]):
    """(ok, normalized_json_or_None). When the schema validates, the second
    element is the extracted value serialized without fences/prose."""
    if schema is None:
        return True, None
    from . import schema as schema_mod

    extracted = schema_mod.extract_json(getattr(turn, "content", "") or "")
    if extracted is None:
        return False, None
    ok, _errs = schema_mod.validate(extracted, schema)
    if ok:
        return True, json.dumps(extracted, indent=2)
    return False, None


def _provider_from_config(cfg: dict, provider_name: Optional[str], model: Optional[str]):
    from .config import ConfigError, resolve_api_key
    from .providers import build_provider

    name = provider_name or cfg.get("default_provider", "local")
    providers = cfg.get("providers", {})
    pconf = providers.get(name)
    if pconf is None:
        raise ExecUsageError(
            f"unknown provider '{name}'. Valid providers: {', '.join(sorted(providers))}"
        )
    if model:
        pconf = {**pconf, "model": model}
    try:
        key = resolve_api_key(cfg, name)
    except ConfigError as exc:
        raise ExecUsageError(str(exc)) from exc
    return name, build_provider(
        protocol=pconf.get("protocol", "openai"),
        base_url=pconf.get("base_url", ""),
        model=pconf.get("model", ""),
        api_key=key,
        timeout=float(cfg.get("timeout_seconds", 300)),
    )


def run_exec(
    prompt: Optional[str],
    *,
    json_mode: bool = False,
    cwd: Optional[Path] = None,
    add_dirs: Optional[list] = None,
    sandbox: Optional[str] = None,
    approval: Optional[str] = None,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    skip_git_repo_check: bool = False,
    ephemeral: bool = False,
    resume_thread: Optional[str] = None,
    max_turns: Optional[int] = None,
    timeout: Optional[int] = None,
    output_last_message: Optional[Path] = None,
    output_schema: Optional[Path] = None,
    ignore_user_config: bool = False,
    bypass: bool = False,
    stream_deltas: bool = True,
    stdin_cm: Optional[str] = None,  # test/dev override: skip reading sys.stdin
) -> int:
    """Run one non-interactive exec turn-group. Returns the exit code."""
    from .config import ConfigError, load_config
    from .loop import run_turns
    from .sandbox import ToolContext
    from . import tools as tool_registry

    workdir = Path(cwd or Path.cwd()).resolve()

    # -- stdin & prompt resolution ------------------------------------
    # stdin_cm special values: None (default) = real sys.stdin handling;
    # "" = treat stdin as an already-empty/captured stream (tests); any
    # other string = that string IS the piped context.
    piped = ""
    if stdin_cm is not None:
        piped = stdin_cm
    elif prompt == "-":
        piped = sys.stdin.read()
        prompt = None
    elif not sys.stdin.isatty():
        piped = sys.stdin.read()

    if prompt:
        full_prompt = (piped.rstrip() + "\n\n" + prompt) if piped.strip() else prompt
    else:
        full_prompt = piped.rstrip("\n")
    if not full_prompt.strip():
        raise ExecUsageError("exec requires a prompt (arg, '-', or piped stdin)")

    # -- git guard -----------------------------------------------------
    if not skip_git_repo_check and find_git_root(workdir) is None:
        raise ExecUsageError(
            f"'{workdir}' is not inside a git repository; "
            "use --skip-git-repo-check to run anyway"
        )

    # -- config & provider ---------------------------------------------
    try:
        cfg = load_config(cwd=workdir, ignore_user_config=ignore_user_config)
    except ConfigError as exc:
        raise ExecUsageError(str(exc)) from exc

    p_name, provider = _provider_from_config(cfg, provider_name, model)
    pconf = cfg["providers"][p_name]

    eff_sandbox = (
        "danger-full-access" if bypass else (sandbox or cfg.get("sandbox", "workspace-write"))
    )
    eff_approval = approval or cfg.get("approval", "on-request")
    eff_max_turns = max_turns or int(cfg.get("max_turns", 30))
    eff_timeout = timeout or int(cfg.get("timeout_seconds", 300))
    tool_protocol = pconf.get("tool_protocol", "auto")

    ctx = ToolContext(
        workdir=workdir,
        sandbox=eff_sandbox,
        add_dirs=[str(Path(d).resolve()) for d in (add_dirs or [])],
        timeout=float(eff_timeout),
        extra={"approval": eff_approval},
    )

    # -- schema (cycle 6) ------------------------------------------------
    schema = _read_schema(output_schema)
    if schema is not None:
        from . import schema as schema_mod

        full_prompt = full_prompt + "\n\n" + schema_mod.schema_instructions(schema)

    thread_id = events.new_thread_id()
    emit = lambda ev: events.emit(ev, json_mode=json_mode)  # noqa: E731
    emit({"type": "thread.started", "thread_id": thread_id})

    # -- event translation: loop events -> codex-style items ------------
    open_items: dict = {}

    def on_event(ev: dict) -> None:
        etype = ev.get("type", "")
        if etype == "tool.started":
            name = ev.get("name", "")
            itype = {
                "shell": "command_execution",
                "write_file": "file_change",
                "edit_file": "file_change",
                "update_plan": "plan",
            }.get(name, "command_execution")
            item = {"id": f"item_{uuid.uuid4().hex[:8]}", "type": itype, "tool": name}
            emit({"type": "thread.item.started", "thread_id": thread_id, "item": item})
            open_items[item["id"]] = item
        elif etype == "tool.completed":
            # close the most recent still-open item for this tool
            item = None
            for iid in reversed(list(open_items)):
                if open_items[iid].get("tool") == ev.get("name", ""):
                    item = open_items.pop(iid)
                    break
            if item is not None:
                emit(
                    {
                        "type": "thread.item.completed",
                        "thread_id": thread_id,
                        "item": item,
                    }
                )
        elif etype == "turn.started":
            emit({"type": "turn.started"})
        elif etype == "turn.completed":
            emit({"type": "turn.completed", "usage": ev.get("usage") or {}})
        elif etype == "notice":
            emit({"type": "notice", "message": ev.get("message", "")})
        elif etype == "error":
            emit({"type": "error", "message": ev.get("message", "")})

    on_token = None
    if stream_deltas and not json_mode:
        def on_token(piece: str) -> None:  # noqa: ANN001
            sys.stderr.write(piece)
            sys.stderr.flush()

    # -- run the agent loop --------------------------------------------
    system_extra = ""
    if eff_sandbox == "danger-full-access" or bypass:
        system_extra = "You have full system access. Commands run with bash -l."
    else:
        system_extra = (
            f"Working directory: {workdir}. Sandbox: {eff_sandbox}. "
            "Write files only inside the working directory."
        )

    emit({"type": "turn.started"})  # opening turn marker (json mode contract)

    # -- session history (resume / new) ----------------------------------
    from . import sessions as sessions_mod

    store = sessions_mod.store(cfg)
    history: list[dict] = []
    if resume_thread:
        try:
            data = store.load(resume_thread)
        except FileNotFoundError as exc:
            raise ExecUsageError(str(exc)) from exc
        history = data["messages"]
        thread_id = resume_thread
    elif not ephemeral:
        store.append_meta(
            thread_id,
            provider=p_name,
            model=getattr(provider, "model", "") or "",
            cwd=str(workdir),
        )

    try:
        turn = run_turns(
            provider,
            full_prompt,
            ctx,
            history=history,
            tool_protocol=tool_protocol,
            system_extra=system_extra,
            max_turns=eff_max_turns,
            stream=stream_deltas,
            on_event=on_event,
            on_token=on_token,
            schema=schema,
        )
    finally:
        try:
            provider.close()
        except Exception:
            pass

    schema_ok, normalized = _schema_turn_check(turn, schema)
    final_text = normalized if (schema_ok and normalized is not None) else (turn.content or "")
    if turn.reasoning:
        emit(
            {
                "type": "thread.item.completed",
                "thread_id": thread_id,
                "item": {
                    "id": f"item_{uuid.uuid4().hex[:8]}",
                    "type": "reasoning",
                    "text": turn.reasoning,
                },
            }
        )
    emit(
        {
            "type": "thread.item.completed",
            "thread_id": thread_id,
            "item": {
                "id": f"item_{uuid.uuid4().hex[:8]}",
                "type": "agent_message",
                "text": final_text,
            },
        }
    )

    # -- stdout: final message (text mode) only -------------------------
    if json_mode:
        # stdout already carried the JSONL events only
        pass
    else:
        if stream_deltas:
            sys.stderr.write("\n")  # close the delta stream line
        sys.stdout.write(final_text + ("\n" if final_text and not final_text.endswith("\n") else ""))
        sys.stdout.flush()

    if output_last_message is not None:
        try:
            Path(output_last_message).write_text(final_text)
        except OSError as exc:
            sys.stderr.write(f"[warn] could not write {output_last_message}: {exc}\n")

    # -- persist session (unless --ephemeral) ------------------------------
    if not ephemeral:
        all_msgs = getattr(turn, "all_messages", None) or history + [
            {"role": "user", "content": full_prompt},
            {"role": "assistant", "content": final_text},
        ]
        try:
            store.append_meta(
                thread_id,
                provider=p_name,
                model=getattr(provider, "model", "") or "",
                cwd=str(workdir),
            )
            for m in all_msgs:
                if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                    store.append_message(thread_id, m["role"], m["content"])
        except OSError as exc:
            sys.stderr.write(f"[warn] could not persist session: {exc}\n")

    return 0 if schema_ok else 1
