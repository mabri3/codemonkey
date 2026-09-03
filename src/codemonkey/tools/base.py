"""Tool base: every tool is `run(args: dict, ctx) -> ToolResult`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

MAX_OUTPUT = 20_000  # tool output truncation (spec)

TRUNCATE_MARKER = "\n\n[... output truncated at {limit} bytes; rerun with narrower args ...]\n"


@dataclass
class ToolResult:
    output: str
    ok: bool = True
    meta: dict = None

    def __post_init__(self):
        if self.meta is None:
            self.meta = {}
        if len(self.output) > MAX_OUTPUT:
            self.output = self.output[:MAX_OUTPUT] + TRUNCATE_MARKER.format(limit=MAX_OUTPUT)


def _err(e: Exception) -> ToolResult:
    return ToolResult(output=f"error: {e}", ok=False)


def _load(path, ctx) -> bytes:
    from ..sandbox import validate_root
    rp = validate_root(ctx, path)
    with open(rp, "rb") as f:
        return f.read()


def _save(path, data, ctx) -> str:
    from ..sandbox import validate_root
    rp = validate_root(ctx, path)
    # Checkpoint PRIOR contents before mutation (loop2 cycle 14). Fails soft:
    # a checkpoint error must never block the write itself.
    try:
        from .. import checkpoints as cp_mod

        if rp.is_file():
            cp = cp_mod.current_checkpoint()  # 14F1: one group per tool call
            cp.snapshot_file(Path(ctx.workdir).resolve(),
                             str(rp.relative_to(Path(ctx.workdir).resolve())),
                             rp.read_bytes())
    except Exception:
        pass
    rp.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        data = data.encode("utf-8")
    with open(rp, "wb") as f:
        f.write(data)
    return str(rp)
