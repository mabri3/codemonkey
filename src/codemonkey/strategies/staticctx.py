"""Static context assembly (loop 38, cycle 75) — the ORIGINAL block assembly
extracted verbatim from exec.py so both strategies share one call shape.

Byte-stability note: exec.py assembles, in order —
  1. build_project_context_block(instructions, memory)   [cycle 18 + 7F1]
  2. job_text appended (or standalone)                   [cycle 44]
  3. repo_map_text appended (or standalone)              [cycle 27]
Each join uses "\\n\\n" and skips empty parts, so the assembled block is
byte-identical to what shipped before the strategy layer existed.
"""

from __future__ import annotations


def assemble_static(task_prompt, fragments, *, job_text: str = "",
                    repo_map_text: str = "", budget: int | None = None) -> str:
    """fragments: [{source, text}] where source in
    {project_context, instructions, memory}. Order is fixed by source role,
    not by content: instructions/memory blocks are pre-joined by the caller
    via build_project_context_block, so `static` receives ONE fragment.

    `budget` is intentionally ignored (static has no budget — that is the
    behavior being A/B-tested)."""
    block = ""
    for f in fragments or []:
        t = str(f.get("text", "")).strip()
        if not t:
            continue
        block = f"{block}\n\n{t}" if block else t
    if job_text:
        block = f"{block}\n\n{job_text}" if block else job_text
    if repo_map_text:
        block = (block + "\n\n" if block else "") + repo_map_text
    return block
