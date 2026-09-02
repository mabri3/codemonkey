"""Interactive REPL (cycle 9).

`codemonkey` with no subcommand opens a chat loop: input() prompt, streaming
deltas to the terminal, slash commands (/quit /clear /model /provider /usage
/sessions). Reasoning (if the model returns some) is hidden by default and
shown with --show-reasoning.

Non-interactive stdin (piped) is ALSO supported: when stdin is not a tty the
REPL reads all lines, runs each prompt, prints final answers — this is the
cycle-9 verify probe path (`printf 'Reply with exactly: fig\n/quit\n' | codemonkey`).
"""

from __future__ import annotations

import sys
from pathlib import Path

from .providers.base import ProviderError

SLASH_COMMANDS = ("/quit", "/exit", "/clear", "/model", "/provider", "/usage", "/sessions", "/help")


class ReplState:
    """Mutable per-session REPL state (slash commands mutate this)."""

    def __init__(self, provider_name: str, model: str):
        self.provider_name = provider_name
        self.model = model
        self.history: list[dict] = []
        self.usage = {"turns": 0, "total_tokens": 0}
        self.cleared_at = 0  # history entries before this index are hidden


def _build_provider(cfg, name: str):
    from .config import resolve_api_key
    from .providers import build_provider

    pconf = cfg.get("providers", {}).get(name)
    if pconf is None:
        raise KeyError(name)
    return build_provider(
        protocol=pconf.get("protocol", "openai"),
        base_url=pconf["base_url"],
        model=pconf.get("model", ""),
        api_key=resolve_api_key(cfg, name) or "",
    )


def handle_slash(state: ReplState, line: str, *, stderr=sys.stderr) -> str:
    """Handle a slash command; returns "quit", "handled", or "chat"."""
    cmd = line.strip()

    if cmd in ("/quit", "/exit"):
        return "quit"
    if cmd == "/clear":
        state.history = []
        state.cleared_at = 0
        print("[cleared conversation history]", file=stderr)
        return "handled"
    if cmd == "/model":
        print(f"{state.provider_name}: {state.model}", file=stderr)
        return "handled"
    if cmd == "/provider":
        print(state.provider_name, file=stderr)
        return "handled"
    if cmd == "/usage":
        print(f"turns: {state.usage['turns']}  total tokens: {state.usage['total_tokens']}",
              file=stderr)
        return "handled"
    if cmd == "/sessions":
        from . import sessions as sessions_mod

        try:
            cfg = {}  # default store; listing is provider-independent
            store = sessions_mod.store(cfg)
            entries = store.list()
        except Exception as exc:
            print(f"[sessions unavailable: {exc}]", file=stderr)
            return "handled"
        if not entries:
            print("(no sessions)", file=stderr)
        for e in entries[-10:]:
            import datetime
            ts = datetime.datetime.fromtimestamp(e.get("updated") or 0).strftime("%m-%d %H:%M")
            print(f"{e['thread_id']}  {ts}", file=stderr)
        return "handled"
    if cmd == "/help":
        print("/quit /clear /model /provider /usage /sessions", file=stderr)
        return "handled"
    return "chat"


def run_repl(
    cfg: dict,
    *,
    provider_name: str = "",
    show_reasoning: bool = False,
    approval: str = "",
    sandbox: str = "",
    bypass: bool = False,
    ephemeral: bool = False,
    stderr=None,
    stdin=None,
    stdout=None,
) -> int:
    """Run the interactive/piped REPL. Returns exit code."""
    err = stderr or sys.stderr
    out = stdout or sys.stdout

    name = provider_name or cfg.get("default_provider", "local")
    pconf = cfg.get("providers", {}).get(name, {})
    state = ReplState(name, pconf.get("model", ""))

    interactive = sys.stdin.isatty()
    if interactive:
        print(f"codemonkey REPL — provider: {name}  model: {state.model}", file=err)
        print("type /help for commands, /quit to exit", file=err)

    try:
        provider = _build_provider(cfg, name)
    except KeyError:
        print(f"error: unknown provider '{name}'", file=err)
        return 2

    def one_turn(user_text: str) -> bool:
        """Run one user turn through the agent loop. False = fatal provider error."""
        from .sandbox import ToolContext
        from .loop import run_turns

        ctx = ToolContext(
            workdir=Path.cwd(),
            sandbox=(bypass and "danger-full-access") or sandbox or cfg.get("sandbox", "workspace-write"),
            timeout=float(cfg.get("timeout_seconds", 300)),
            extra={"approval": approval or cfg.get("approval", "on-request")},
        )
        eff_approval = approval or cfg.get("approval", "on-request") or "never"
        state.history.append({"role": "user", "content": user_text})
        try:
            turn = run_turns(
                provider, user_text, ctx,
                history=state.history[:-1],
                tool_protocol=pconf.get("tool_protocol", "auto"),
                system_extra="",
                max_turns=int(cfg.get("max_turns", 30)),
                stream=True,
                # deltas stream to stderr live; only the final message goes to stdout
                on_token=lambda tok: (err.write(tok), err.flush()),
                approval=eff_approval,
            )
        except ProviderError as exc:
            print(f"[provider error: {exc}]", file=err)
            state.history.pop()  # don't keep the unservable user message
            return True
        finally:
            state.usage["turns"] += 1

        state.usage["total_tokens"] += int((getattr(turn, "usage", {}) or {}).get("total_tokens", 0) or 0)
        content = (turn.content or "").strip()
        # hide a reasoning-style prefix unless --show-reasoning
        if not show_reasoning:
            content = strip_reasoning(content)
        if content:
            out.write("\n" + content + "\n")
            out.flush()
        state.history.append({"role": "assistant", "content": content})
        return True

    # main loop
    if not interactive:
        lines = [ln.rstrip("\n") for ln in sys.stdin]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("/"):
                if handle_slash(state, line, stderr=err) == "quit":
                    break
                continue
            ok = one_turn(line)
            if not ok:
                return 1
        return 0

    # interactive
    while True:
        try:
            line = input("you> ")
        except (EOFError, KeyboardInterrupt):
            print(file=err)
            return 0
        line = line.strip()
        if not line:
            continue
        if line.startswith("/"):
            if handle_slash(state, line, stderr=err) == "quit":
                return 0
            continue
        one_turn(line)


def strip_reasoning(content: str) -> str:
    """Best-effort: drop think-tags and leading whitespace."""
    import re

    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
    return content.lstrip()
