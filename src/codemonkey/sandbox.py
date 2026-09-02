"""Sandbox policy for codemonkey tool execution.

Three sandbox levels (config `sandbox` / `--sandbox`):

  read-only           : read-only tools allowed; every write + shell DENIED.
  workspace-write     : writes allowed only inside the allowed roots
                        (cwd + `--add-dir`s); shell ALLOWED per policy
                        (spec:97) — cwd-bound, and callers should pair it
                        with an approval policy (e.g. `approval: never` for
                        auto-approve); the full approval layer is cycle 8.
  danger-full-access  : everything allowed (shell + arbitrary paths).

The `--dangerously-bypass-approvals-and-sandbox` flag resolves to
`danger-full-access` at the config layer.

Containment is lexical (normalized, `..`-aware) — it never follows symlinks
out of the roots, which is what we want for a default workspace.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

LEVELS = ("read-only", "workspace-write", "danger-full-access")

_READ_TOOLS = frozenset(
    {"read_file", "list_dir", "glob", "search", "update_plan", "web_fetch"}
)
_WRITE_TOOLS = frozenset({"write_file", "edit_file"})
_SHELL_TOOLS = frozenset({"shell"})


class SandboxError(Exception):
    """Raised when a tool call violates the sandbox policy."""


@dataclass
class ToolContext:
    """Per-execution context handed to every tool."""

    workdir: Path
    sandbox: str = "workspace-write"
    add_dirs: list = field(default_factory=list)
    timeout: float = 120.0
    extra: dict = field(default_factory=dict)

    @property
    def roots(self) -> list[Path]:
        """Absolute, normalized allowed write/read roots (cwd first)."""
        roots = [Path(self.workdir).resolve()]
        for d in self.add_dirs:
            roots.append(Path(d).resolve())
        return roots

    def resolve(self, path) -> Path:
        """Resolve `path` (abs or cwd-relative) and require it inside a root."""
        p = Path(path)
        if not p.is_absolute():
            p = Path(self.workdir) / p
        rp = p.resolve()
        for root in self.roots:
            if rp == root or root in rp.parents:
                return rp
        raise SandboxError(f"path '{path}' is outside allowed roots")


def can(tool: str, level: str) -> bool:
    """Coarse gate: is `tool` permitted at `level` at all?"""
    if level not in LEVELS:
        raise SandboxError(f"unknown sandbox level '{level}'")
    if tool in _SHELL_TOOLS:
        # spec:97 — workspace-write allows shell per policy (spec text:
        # "shell allowed per policy"). Approval-gating / soft-deny of shell
        # is the approvals layer (CYCLE 8); the sandbox is not the gate.
        return level in ("workspace-write", "danger-full-access")
    if tool in _WRITE_TOOLS:
        return level in ("workspace-write", "danger-full-access")
    if tool in _READ_TOOLS:
        return True
    # unknown tools: only allowed at full access
    return level == "danger-full-access"


def check(tool: str, ctx: "ToolContext") -> None:
    """Raise SandboxError if `tool` is not permitted for ctx.sandbox."""
    if not can(tool, ctx.sandbox):
        if tool in _SHELL_TOOLS:
            raise SandboxError(
                f"shell is not permitted under sandbox '{ctx.sandbox}' "
                "(danger-full-access required)"
            )
        if tool in _WRITE_TOOLS:
            raise SandboxError(
                f"{tool} is not permitted under sandbox 'read-only'"
            )
        raise SandboxError(f"{tool} not permitted under sandbox '{ctx.sandbox}'")


def validate_root(ctx: "ToolContext", path) -> Path:
    """For path-scoped tools: resolve + ensure inside a root."""
    return ctx.resolve(path)
