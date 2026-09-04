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
- events             thread.started{thread_id} → turn.* / item.* →
                     turn.completed{usage} (see events.py)
"""

from __future__ import annotations

import json
import os
import re
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
        max_retries=int(cfg.get("max_retries", 3) or 0),
    )


def _read_optional_stdin(timeout: float = 0.25) -> str:
    """Read piped stdin only when the stream actually has something waiting.

    select() distinguishes "data (or EOF) is ready" from "a writer is holding
    the pipe open with nothing to say". Redirected files and real pipelines
    report ready immediately, so `cat notes.txt | codemonkey exec "summarize"`
    keeps working; an idle inherited pipe returns "" instead of hanging.
    """
    try:
        fileno = sys.stdin.fileno()
    except Exception:
        # In-memory stream (StringIO under CliRunner, captured pipes in
        # tests): nothing to wait on and read() cannot block, so just read.
        try:
            return sys.stdin.read()
        except Exception:  # pragma: no cover
            return ""
    try:
        import select

        ready, _, _ = select.select([fileno], [], [], timeout)
    except Exception:  # pragma: no cover - platforms without select-on-pipes
        return ""
    if not ready:
        return ""
    try:
        return sys.stdin.read()
    except Exception:  # pragma: no cover
        return ""


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
    project_instructions: Optional[bool] = None,
    stream_deltas: bool = True,
    stdin_cm: Optional[str] = None,  # test/dev override: skip reading sys.stdin
    event_sink=None,  # test/dev: collect JSONL events into a list,
    cost_summary: bool = False,
    emit_fn=None,  # override for tests: (event_dict) -> None
    job_id: str = "",
    verify_claims: bool = False,
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
        # 51F3: a prompt argument makes piped stdin OPTIONAL context, so this
        # must not block on a pipe that is open but idle. Supervisors, CI
        # runners and agent harnesses routinely hand a child an inherited pipe
        # nobody ever writes to or closes; the old unconditional read() hung
        # such runs forever — squarely the unattended case codemonkey targets.
        # With no prompt argument stdin is the ONLY source, so still block.
        piped = _read_optional_stdin() if prompt else sys.stdin.read()

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

    # memory (7F1): resolve before ctx so update_memory can reach the store
    try:
        from .strategies import select_strategy as _sel_mem

        mem_name = _sel_mem("memory", cfg)
    except Exception:
        mem_name = "file"
    memory_enabled = mem_name != "none"
    memory_obj = None
    memory_text = ""
    if memory_enabled:
        try:
            from .strategies.memory import get_memory as _get_memory

            memory_obj = _get_memory(mem_name)
            memory_text = memory_obj.load() or ""
        except Exception:
            memory_obj = None
            memory_text = ""

    ctx = ToolContext(
        workdir=workdir,
        sandbox=eff_sandbox,
        add_dirs=[str(Path(d).resolve()) for d in (add_dirs or [])],
        timeout=float(eff_timeout),
        extra={"approval": eff_approval, "config": cfg, "memory": memory_obj},
    )

    # -- schema (cycle 6) -----------------------------------------------
    # The schema instructions are injected for the MODEL, but the pristine
    # prompt is what gets persisted to the session store (resumed threads
    # must not replay stale schema scaffolding — critic finding 6F2).
    schema = _read_schema(output_schema)
    persist_prompt = full_prompt
    if schema is not None:
        from . import schema as schema_mod

        full_prompt = full_prompt + "\n\n" + schema_mod.schema_instructions(schema)

    thread_id = events.new_thread_id()
    run_id = uuid.uuid4().hex[:8]  # 31F1: journal idempotency scope
    _emit_base = emit_fn or (lambda ev: events.emit(ev, json_mode=json_mode))

    def emit(ev: dict) -> None:
        if event_sink is not None:
            event_sink.append(ev)
        _emit_base(ev)

    emit({"type": "thread.started", "thread_id": thread_id})

    # -- event translation: loop events -> codex-style items ------------
    open_items: dict = {}
    history_len = 0  # set after session load; used by the persist.drop hook
    persist_pruned = {"done": False}  # 7F2: set when persist.drop pruned in place

    if cost_summary and event_sink is None:
        event_sink = []  # telemetry needs a collector even without --json
    _external_events = event_sink if event_sink is not None else None

    def on_event(ev: dict) -> None:
        if _external_events is not None:
            _external_events.append(ev)
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
            # 51F5: fill the fields the renderer already reads, so the trace
            # names the command / file instead of printing `$ ` forever.
            targs = ev.get("args") or {}
            if itype == "command_execution":
                item["command"] = str(targs.get("command", ""))[:500]
            elif itype == "file_change":
                item["path"] = str(targs.get("path", ""))[:500]
            emit({"type": "item.started", "thread_id": thread_id, "item": item})
            open_items[item["id"]] = item
        elif etype == "tool.completed":
            # close the most recent still-open item for this tool
            item = None
            for iid in reversed(list(open_items)):
                if open_items[iid].get("tool") == ev.get("name", ""):
                    item = open_items.pop(iid)
                    break
            if item is not None:
                if item.get("type") == "command_execution":
                    out = ev.get("output") or ""
                    # shell reports a real failure as "exit N\n<output>";
                    # prefer that code over a synthesized 0/1 so the trace
                    # doesn't quietly relabel `exit 3` as `exit 1`.
                    m = re.match(r"exit (\d+)\n", out)
                    if m:
                        item["exit_code"] = int(m.group(1))
                        item["aggregated_output"] = out[m.end():]
                    else:
                        item["exit_code"] = 0 if ev.get("ok") else 1
                        item["aggregated_output"] = out
                emit(
                    {
                        "type": "item.completed",
                        "thread_id": thread_id,
                        "item": item,
                    }
                )
        elif etype == "turn.started":
            emit({"type": "turn.started", "thread_id": thread_id})
        elif etype == "turn.completed":
            emit({"type": "turn.completed", "usage": ev.get("usage") or {}})
        elif etype == "notice":
            emit({"type": "notice", "message": ev.get("message", "")})
        elif etype == "error":
            emit({"type": "error", "message": ev.get("message", "")})
        elif etype == "persist.drop":
            # 6F2: pruning hook emitted by the loop right before
            # all_messages is frozen; carries the first-run messages by
            # reference so exec can strip pre-run history + retry scaffolding
            # and persist only the pristine first user prompt.
            msgs = ev.get("messages")
            if isinstance(msgs, list):
                del msgs[: history_len]
                persist_pruned["done"] = True
                if msgs and msgs[0].get("content") == full_prompt:
                    msgs[0] = {**msgs[0], "content": persist_prompt}
                meta = ev.get("meta") or {}
                drop = meta.get("drop_tail") or 0
                if drop:
                    del msgs[-drop:]
                replacement = meta.get("replace_with")
                if replacement is not None:
                    msgs.append({"role": "assistant", "content": replacement})

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

    # -- project instructions (loop4, cycle 18) --------------------------
    # Gate precedence: CLI flag (--no-project-instructions) > env > config
    # (load_config already applied env). None = no CLI override.
    pi_enabled = cfg.get("project_instructions", True)
    if project_instructions is not None:
        pi_enabled = project_instructions
    # loop12 cycle 44: job-aware injection
    job_text = ""
    job_id_arg = job_id
    if job_id_arg:
        from .jobs import load as _job_load, render as _job_render

        _job = _job_load(job_id_arg)
        if _job is None:
            raise ExecUsageError(f"--job: no such job: {job_id_arg}")
        job_text = _job_render(_job)

    repo_map_text = ""
    if cfg.get("repo_map", False):
        try:
            from . import repomap as _rm

            rmap = _rm.scan_repo(Path(workdir))
            # cycle 27: task-conditioned relevance — derive query terms from
            # the user prompt (words >=4 chars, lowercased, deduped).
            _prompt_words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", full_prompt or "")
            _seen_terms: set[str] = set()
            _query_terms = [w.lower() for w in _prompt_words
                            if not (w.lower() in _seen_terms or _seen_terms.add(w.lower()))]
            repo_map_text = _rm.render_injection(
                rmap, Path(workdir),
                budget=int(cfg.get("repo_map_budget", 4000) or 4000),
                query_terms=_query_terms[:40],
            )
        except Exception:
            repo_map_text = ""

    if pi_enabled or memory_text or repo_map_text:
        from .instructions import build_project_context_block, load_instructions

        instr_text = load_instructions(Path(workdir), enabled=pi_enabled) if pi_enabled else ""
        block = build_project_context_block(
            Path(workdir), instructions=instr_text, memory_text=memory_text
        )
        if job_text:
            block = f"{block}\n\n{job_text}" if block else job_text
        if repo_map_text:
            block = (block + "\n\n" if block else "") + repo_map_text
        if block:
            system_extra = system_extra + "\n\n" + block

    # -- session history (resume / new) ----------------------------------
    from . import sessions as sessions_mod

    # loop2 cycle 15: registry-selected compaction strategy for auto-compaction
    from .strategies import select_strategy as _sel_strat
    from .strategies.compaction import get_compactor as _get_compactor

    try:
        _comp_name = _sel_strat("compaction", cfg)
        compaction = _get_compactor(_comp_name, cfg)
    except Exception:
        compaction = None  # fail-soft: never block exec on strategy wiring

    store = sessions_mod.store(cfg)
    history: list[dict] = []
    if resume_thread:
        try:
            data = store.load(resume_thread)
        except FileNotFoundError as exc:
            raise ExecUsageError(str(exc)) from exc
        history = data["messages"]
        thread_id = resume_thread
        history_len = len(history)
    elif not ephemeral:
        store.append_meta(
            thread_id,
            provider=p_name,
            model=getattr(provider, "model", "") or "",
            cwd=str(workdir),
        )

    def _attempt(prov):
        return run_turns(
            prov,
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
            approval=eff_approval,
            context_limit=int(cfg.get("context_limit", 32000) or 0) or None,
            compaction=compaction,
            verify_command=(str(cfg.get("verify_command") or "").strip() or None),
            max_verify_retries=int(cfg.get("max_verify_retries", 1) or 0),
            memory_enabled=memory_enabled,
            max_edit_retries=int(cfg.get("max_edit_retries", 1) or 0),
            observation_budget=int(cfg.get("observation_budget", 24000) or 0),
            prompt_cache=bool(cfg.get("prompt_cache", True)),
            # 31F1: the loop-7 journal was never given a thread by any
            # production caller, so intents/outcomes/idempotent replay were
            # inert outside the unit tests. The session thread id names the
            # journal file; a per-invocation run id scopes the idempotency key
            # so a resumed thread cannot replay an earlier run's write.
            journal_thread=thread_id,
            journal_run=run_id,
            perm_rules=list(((cfg.get("permissions") or {}).get("rules")) or []),
        )

    # loop14 cycle 47: availability failover — after transport/timeout errors
    # exhaust retries, re-run against fallback_provider (if configured and
    # existing). Auth and tools-500 never fail over (wrong-credentials and
    # protocol-rejection are not availability problems).
    _fall_name = (cfg.get("fallback_provider") or "").strip()
    _attempt_provs = [provider]
    if _fall_name:
        _fp = (cfg.get("providers") or {}).get(_fall_name)
        if _fp is None:
            raise ExecUsageError(
                f"fallback_provider '{_fall_name}' is not defined. "
                f"Valid providers: {', '.join(cfg.get('providers', {}))}")
        if _fall_name != p_name:
            pass  # fallback provider built lazily only if the primary fails
    try:
        turn = _attempt(provider)
    except Exception as _exc:
        _err_text = str(_exc).lower()
        _transport = ("transport" in _err_text or "timeout" in _err_text
                      or "timed out" in _err_text or "deadline" in _err_text)
        _auth = ("auth" in _err_text or "401" in _err_text or "403" in _err_text)
        _tools_rej = "tools parameter" in _err_text
        if (_fall_name and _transport and not _auth and not _tools_rej
                and _fall_name != p_name
                and (cfg.get("providers") or {}).get(_fall_name)):
            if on_event:
                on_event({"type": "notice",
                          "message": f"failover: primary failed ({type(_exc).__name__}); "
                                     f"retrying against fallback_provider '{_fall_name}'"})
            try:
                from .journal import classify_error as _ce, record as _jr

                _jr(thread_id, "outcome", tool="failover", key=run_id + ":failover",
                    status="switch", error_class=_ce(_exc))
            except OSError:
                pass
            _fb_name, _fb = _provider_from_config(cfg, _fall_name, model)
            try:
                turn = _attempt(_fb)
            finally:
                try:
                    _fb.close()
                except Exception:
                    pass
        else:
            raise
    finally:
        try:
            provider.close()
        except Exception:
            pass

    schema_ok, normalized = _schema_turn_check(turn, schema)
    if verify_claims:
        try:
            from .claims import annotate as _vc_annotate

            final_text_pre = normalized if (schema_ok and normalized is not None) else (turn.content or "")
            _annotated, _vc_res = _vc_annotate(final_text_pre, workdir=Path(workdir), thread_id=thread_id)
            if _vc_res["unverified"]:
                if schema_ok and normalized is not None:
                    normalized = _annotated
                else:
                    turn.content = _annotated
        except OSError:
            pass
    final_text = normalized if (schema_ok and normalized is not None) else (turn.content or "")
    if turn.reasoning:
        emit(
            {
                "type": "item.completed",
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
            "type": "item.completed",
            "thread_id": thread_id,
            "item": {
                "id": f"item_{uuid.uuid4().hex[:8]}",
                "type": "agent_message",
                "text": final_text,
            },
        }
    )

    # -- spill hygiene (loop6, cycle 30): prune stale spill files ----------
    try:
        from .spill import prune as _spill_prune

        _spill_prune()
    except OSError:
        pass

    # -- job step write-back (loop12, cycle 44) ---------------------------
    if job_id_arg and not ephemeral:
        try:
            from .jobs import set_step as _job_set

            _all = getattr(turn, "all_messages", []) or []
            _texts = [str(m.get("content", "")) for m in _all
                      if m.get("role") == "assistant"]
            _combined = "\n".join(_texts)
            for m in re.finditer(
                    r"JOB_STEP\s+(\S+)\s+(done|failed)(?:\s+--\s*([^\n]*))?", _combined):
                _job_set(job_id_arg, m.group(1), m.group(2),
                         (m.group(3) or "").strip())
        except OSError:
            pass

    # -- cost telemetry (loop5, cycle 26) --------------------------------
    if cost_summary and event_sink is not None:
        import time as _t

        from .cost import append_to_ledger, render_summary, summarize

        wall = getattr(events, "wall", 0.0)
        summary = summarize(event_sink, wall_seconds=wall)
        sys.stderr.write(render_summary(summary) + "\n")
        try:
            append_to_ledger(summary, thread_id=thread_id)
        except OSError as exc:
            sys.stderr.write(f"[warn] cost ledger write failed: {exc}\n")

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
    # 7F2 (critic-loop8 finding 1): the loop returns history + THIS run, and
    # the store is append-only — persisting the whole stack re-wrote a resumed
    # thread's history on every resume (2^n growth). Append only what this run
    # produced, and append the closing assistant answer exactly once (the loop
    # never puts the final answer into `messages`).
    if not ephemeral:
        all_msgs = getattr(turn, "all_messages", None)
        if all_msgs is None:
            new_msgs = [{"role": "user", "content": persist_prompt}]
        elif persist_pruned["done"]:
            # the persist.drop hook already stripped the prior history in place
            new_msgs = list(all_msgs)
        elif list(all_msgs[:history_len]) == list(history):
            new_msgs = list(all_msgs[history_len:])
        else:
            # the prefix no longer matches (auto-compaction rewrote the stack):
            # index slicing is not trustworthy, so persist the minimal honest
            # pair instead of guessing which messages are new.
            new_msgs = [{"role": "user", "content": persist_prompt}]
        if new_msgs and new_msgs[0].get("content") == full_prompt:
            new_msgs[0] = {**new_msgs[0], "content": persist_prompt}
        while new_msgs and new_msgs[-1].get("role") == "assistant":
            new_msgs.pop()
        new_msgs.append({"role": "assistant", "content": final_text})
        try:
            store.append_meta(
                thread_id,
                provider=p_name,
                model=getattr(provider, "model", "") or "",
                cwd=str(workdir),
            )
            for m in new_msgs:
                if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                    store.append_message(thread_id, m["role"], m["content"])
        except OSError as exc:
            sys.stderr.write(f"[warn] could not persist session: {exc}\n")

    return 0 if schema_ok else 1