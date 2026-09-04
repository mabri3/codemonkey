"""Context strategies (loop 38, cycle 75) — how the system-prompt context
block is assembled.

Two selectable strategies, chosen like every strategy domain
(env > config > default; unknown name -> exit-2 surface):

  static (default): today's byte-stable assembly — instructions block +
  memory block, then job text, then the repo-map injection, concatenated in
  exec.py exactly as shipped in cycles 18/27/44. NOTHING changes for
  existing users.

  learned (loop 36, learnedctx.py): the same fragment sources ranked by
  learned utility (class weight × task overlap × recency decay) under a
  token budget — the A/B-measurable variant. Off by default.
"""

from __future__ import annotations

from typing import Optional

from .. import learnedctx
from .staticctx import assemble_static

VALID_CONTEXT = ("static", "learned")


def get_context_assembler(name: str, cfg: Optional[dict] = None):
    """Return fn(task_prompt, fragments, *, budget) -> assembled block text.

    Unknown names raise ValueError (the strategies layer maps that to the
    exit-2 surface listing valid names, same as memory/compaction).
    """
    if name == "static":
        return assemble_static
    if name == "learned":
        budget = int((cfg or {}).get("context_budget", 600) or 600)

        def _learned(task_prompt, fragments, *, job_text: str = "",
                    repo_map_text: str = "", budget=budget):
            frags = list(fragments)
            if job_text:
                frags.append({"source": "job", "text": job_text})
            if repo_map_text:
                frags.append({"source": "repo_map", "text": repo_map_text})
            res = learnedctx.assemble(task_prompt or "", frags, token_budget=budget)
            parts = [f["text"].strip() for f in res["selected"] if f.get("text", "").strip()]
            return "\n\n".join(parts)

        return _learned
    raise ValueError(
        f"unknown context strategy '{name}'. "
        f"Valid context strategies: {', '.join(VALID_CONTEXT)}"
    )
