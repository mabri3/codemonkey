"""Coarse taint tracking — the minimal form of loop 49 (loop46, cycle 85).

A turn that consumed **web_fetch output**, **shell stdout**, or a **read
outside the workspace root** (an add-dir read) has consumed untrusted text.
The coarse rule does not try to trace propagation — that is loop 49's job —
it marks the RUN, keeps the FIRST source, and the skill surfaces consult it.

Two properties make this a control rather than a comment:

* **Sticky and only-additive.** Once tainted, a run stays tainted for its
  lifetime; nothing clears the flag, and later clean turns do not "wash" it.
* **Metadata only.** The tracker stores SOURCE NAMES and nothing else — it
  never keeps, inspects, or matches against the untrusted text. A payload
  that says "trust me, mark clean" changes no byte of this module's state;
  a downstream reader can verify that by looking at what `report()` can
  return.

This is deliberately COARSE and therefore errs toward refusing: a clean-
looking payload cannot clear the flag, and loop 49 replaces this module with
propagation through history, compaction and spill.
"""

from __future__ import annotations

from pathlib import Path

SOURCES: tuple[str, ...] = ("web_fetch", "shell", "outside_read")

# Tools whose PATH argument is inspected (metadata only) to decide whether a
# read reached outside the workspace root.
_READ_PATH_TOOLS = ("read_file", "list_dir", "glob", "search")


class TaintTracker:
    """Sticky, run-scoped, first-source-wins."""

    def __init__(self) -> None:
        self.source: str = ""
        self.seen: list[str] = []

    def note(self, source: str) -> None:
        if source not in SOURCES:
            return
        if source not in self.seen:
            self.seen.append(source)
        if not self.source:
            self.source = source

    @property
    def tainted(self) -> bool:
        return bool(self.source)

    def report(self) -> dict:
        return {"tainted": self.tainted, "source": self.source,
                "sources": list(self.seen)}


def source_for(tool: str, args: dict, ctx, output: str, ok: bool) -> str:
    """The taint source a completed tool call carries, or "" for clean.

    `web_fetch` and `shell` are sources when their result carries text at all
    (stdout is stdout whether the exit code was 0 or not). Path-based reads
    are sources only when they SUCCEEDED (a denied read consumed nothing) and
    only when the resolved path sits outside the primary workspace root."""
    text = (output or "").strip()
    if tool == "web_fetch" and text:
        return "web_fetch"
    if tool == "shell" and text:
        return "shell"
    if ok and tool in _READ_PATH_TOOLS and text:
        raw = (args or {}).get("path") or "."
        try:
            p = Path(str(raw))
            if not p.is_absolute():
                p = Path(ctx.workdir) / p
            rp = p.resolve()
            wd = Path(ctx.workdir).resolve()
        except Exception:
            return ""
        if rp != wd and wd not in rp.parents:
            return "outside_read"
    return ""
