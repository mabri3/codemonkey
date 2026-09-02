"""Memory strategies (cycle 7): pluggable, config-selected.

Protocol:
    load() -> str          # text injected into the system prompt ("" if empty)
    add_fact(text) -> None # persist a durable fact

  - file (default): ~/.codemonkey/memory.md — markdown list of facts,
    injected verbatim into the system prompt, exposed as the update_memory
    tool surface.
  - none: no memory; load() -> "", add_fact() is a no-op.
"""

from __future__ import annotations

from pathlib import Path


def _memory_path() -> Path:
    d = Path.home() / ".codemonkey"
    d.mkdir(parents=True, exist_ok=True)
    return d / "memory.md"


class FileMemory:
    """Markdown-file memory store (default)."""

    name = "file"

    def __init__(self, path: Path | None = None):
        self.path = path or _memory_path()

    def load(self) -> str:
        if not self.path.is_file():
            return ""
        text = self.path.read_text()
        return text.strip()

    def add_fact(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        existing = self.load()
        if existing:
            if text in existing.splitlines():
                return  # idempotent: no duplicate facts
            self.path.write_text(existing.rstrip() + "\n" + text + "\n")
        else:
            self.path.write_text(text + "\n")


class NoMemory:
    """Memory disabled: load() -> "", add_fact() is a no-op."""

    name = "none"

    def load(self) -> str:
        return ""

    def add_fact(self, text: str) -> None:
        return None


_MEMORY = {
    "file": FileMemory,
    "none": NoMemory,
}

VALID_MEMORY = sorted(_MEMORY)


def get_memory(name: str, path: Path | None = None):
    """Instantiate a memory strategy by config name (unknown -> ValueError)."""
    if name not in _MEMORY:
        raise ValueError(
            f"unknown memory strategy '{name}'. "
            f"Valid memory strategies: {', '.join(VALID_MEMORY)}"
        )
    return _MEMORY[name](path) if name == "file" else _MEMORY[name]()

