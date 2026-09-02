"""Approval policy layer (cycle 8).

Policies (config `approval` / `--approval`, default `on-request`):

  untrusted   : shell AND write tools need approval (most restrictive).
  on-request  : shell needs approval; write tools inside the workspace roots
                are fine (sandbox already bounds them).
  never       : auto-approve everything the sandbox allows (non-interactive
                default for CI/scripted runs).

Decisions come back as one of:
  "allow"      — run the tool.
  "soft-deny"  — do NOT run it; emit a stderr notice (tool + how to allow)
                 and feed the model an approval-required tool result so the
                 run continues (exec non-interactive behavior).
  "ask"        — interactive prompt (REPL path; exec maps ask -> soft-deny).

`--dangerously-bypass-approvals-and-sandbox` (bypass=True) lifts BOTH layers:
every decision returns allow, and the sandbox resolves to danger-full-access
(exec.py already does the sandbox half).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

WRITE_TOOLS = frozenset({"write_file", "edit_file"})
SHELL_TOOLS = frozenset({"shell"})

ALLOW = "allow"
SOFT_DENY = "soft-deny"
ASK = "ask"

POLICIES = ("untrusted", "on-request", "never")


@dataclass
class Decision:
    action: str          # ALLOW | SOFT_DENY | ASK
    reason: str = ""

    @property
    def notice(self) -> str:
        """Human-facing notice explaining the gate and how to allow it."""
        if self.action == ALLOW:
            return ""
        how = (
            'run with `--approval never` (or set approval: never in config) '
            "to auto-approve, or `--dangerously-bypass-approvals-and-sandbox` "
            "to lift both gates"
        )
        return f"[codemonkey] approval required: {self.reason}. Continued without running it. To allow: {how}"


def decide(tool: str, approval: str, *, sandbox: str = "workspace-write",
           bypass: bool = False, interactive: bool = False) -> Decision:
    """Evaluate the approval policy for `tool`."""
    if bypass:
        return Decision(ALLOW, "bypass flag lifts approvals")
    if approval not in POLICIES:
        return Decision(SOFT_DENY, f"unknown approval policy '{approval}'")

    if approval == "never":
        return Decision(ALLOW, "approval: never auto-approves")

    gated = []  # which categories this policy gates
    if approval == "on-request":
        gated = list(SHELL_TOOLS)
    elif approval == "untrusted":
        gated = list(SHELL_TOOLS) + list(WRITE_TOOLS)

    if tool in gated:
        # danger-full-access means the operator already opted out of limits;
        # treat it as pre-approved for shell (writes were never gated here).
        if sandbox == "danger-full-access":
            return Decision(ALLOW, "danger-full-access pre-approves")
        if interactive:
            return Decision(ASK, f"'{tool}' needs approval ({approval})")
        return Decision(SOFT_DENY, f"'{tool}' needs approval (policy: {approval})")

    return Decision(ALLOW, "not gated by this policy")


def notice_to_stderr(decision: Decision, stream=None) -> None:
    """Emit the soft-deny notice on stderr (exec path).

    `sys.stderr` is resolved at call time (not import time) so capture
    machinery (pytest capsys, exec's stderr redirections) sees the notice.
    """
    if decision.action == SOFT_DENY and decision.notice:
        import sys as _sys

        target = stream or _sys.stderr
        target.write(decision.notice + "\n")


def tool_result_notice(tool: str, decision: Decision) -> str:
    """The TOOL_RESULT text fed back to the model on a soft-deny."""
    if decision.action == SOFT_DENY:
        return (
            f"error: tool '{tool}' was NOT executed — approval required "
            f"({decision.reason}). Do not retry the same call; finish with "
            "your best answer without it."
        )
    return ""
