"""Project-instruction loading (loop4, cycle 18).

Loads the project's agent instructions so the model operates inside the
project's own contract (AGENTS.md being the canonical example — this repo
dogfoods it).

Discovery (nearest-first from the workdir upward to the repo root; nearest
wins):
  1. AGENTS.md
  2. CLAUDE.md
  3. .codemonkey/instructions.md

  32KB cap with an explicit ``[truncated at 32KB]`` marker (revocable by
  config). Gates:

  - config ``project_instructions: true`` (default)
  - env ``CODEMONKEY_PROJECT_INSTRUCTIONS``
  - CLI ``--no-project-instructions``

The loaded text merges with the memory strategy text into ONE stable
project-context block prepended to the system prompt.
"""

from __future__ import annotations

from pathlib import Path

MAX_INSTRUCTION_BYTES = 32 * 1024
TRUNCATION_MARKER = "[truncated at 32KB]"
CANDIDATES = ("AGENTS.md", "CLAUDE.md", ".codemonkey/instructions.md")


def find_instructions_file(workdir: Path) -> Path | None:
    """Nearest-first walk from workdir up to (and including) the git root.

    For each directory, check AGENTS.md, CLAUDE.md, .codemonkey/instructions.md
    in that order. The FIRST hit wins (nearest directory beats repo root).
    """
    d = Path(workdir).resolve()
    # cap the ascent at the git root (or filesystem root if not a repo)
    stop = d
    probe = d
    while probe != probe.parent:
        if (probe / ".git").exists():
            stop = probe
            break
        probe = probe.parent
    cur = d
    while True:
        for name in CANDIDATES:
            p = cur / name
            if p.is_file():
                return p
        if cur == stop or cur == cur.parent:
            return None
        cur = cur.parent


def load_instructions(workdir: Path, *, enabled: bool = True,
                      max_bytes: int = MAX_INSTRUCTION_BYTES) -> str:
    """Load + size-cap instruction text. Disabled or absent -> ""."""
    if not enabled:
        return ""
    src = find_instructions_file(workdir)
    if src is None:
        return ""
    try:
        raw = src.read_bytes()
    except OSError:
        return ""
    if len(raw) > max_bytes:
        return raw[:max_bytes].decode("utf-8", errors="replace") + "\n" + TRUNCATION_MARKER
    return raw.decode("utf-8", errors="replace")


def build_project_context_block(workdir: Path, *, instructions: str = "",
                                memory_text: str = "") -> str:
    """ONE stable project-context block (cycle 18 + 7F1 groundwork).

    Order inside the block: instructions first, then memory facts. Empty
    inputs are skipped so the block is absent (not empty) when there is
    nothing to say — keeps the system prompt byte-stable otherwise.
    """
    parts = []
    if instructions and instructions.strip():
        parts.append("## Project instructions\n\n" + instructions.strip())
    if memory_text and memory_text.strip():
        parts.append("## Memory\n\n" + memory_text.strip())
    return "\n\n".join(parts)
