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

  playbook (loop 47, cycle 109): the static assembly PLUS a block rendered
  from the playbook store's ADMITTED entries — quarantined and evicted
  entries never render (R-J; proven by byte-diff). The block is filled
  greedily under `playbook_budget` (env CODEMONKEY_PLAYBOOK_BUDGET); the
  budget is enforced BEFORE rendering — an entry that does not fit is
  excluded whole and its text never reaches the prompt — and an absent
  budget means UNLIMITED, which the printed accounting line SAYS (a budget
  that is only reported is not a budget; a zero is never a stand-in for
  "unset").
"""

from __future__ import annotations

import os
from typing import Optional

from .. import learnedctx
from .staticctx import assemble_static

VALID_CONTEXT = ("static", "learned", "playbook")

PB_HEADER = "## Playbook (admitted)"


def playbook_block_and_account(workdir, cfg: Optional[dict] = None):
    """Render the admitted-entries block + its accounting line.

    Returns `(block_text, account_line)`. The block is empty when nothing is
    admitted, when no entry fits the budget, or when the store is corrupt
    (the account line then says exactly why — fail closed AND audible).
    Budget unit: WORDS, the same unit learnedctx counts."""
    from .. import playbook as pb

    raw = (cfg or {}).get("playbook_budget")
    if raw in (None, ""):
        budget = None
    else:
        try:
            budget = int(raw)
        except (TypeError, ValueError):
            return "", (f"[playbook] injection skipped: playbook_budget "
                        f"{raw!r} is not a number")
    env_note = (" (CODEMONKEY_PLAYBOOK_BUDGET)"
                if os.environ.get("CODEMONKEY_PLAYBOOK_BUDGET") not in (None, "")
                else "")
    try:
        entries = pb.load_admitted(workdir)
    except pb.PlaybookError as exc:
        return "", f"[playbook] injection REFUSED: {exc}"
    if not entries:
        b = "unlimited" if budget is None else f"{budget} words{env_note}"
        return "", f"[playbook] 0 admitted entries; budget: {b}"
    chosen: list[str] = []
    used = 0
    for e in entries:
        line = f"- [{e['kind']}/{e['section']}] {e['text']}"
        cost = len(line.split())
        if budget is not None and used + cost > budget:
            continue  # enforced before the spend: this entry never renders
        chosen.append(line)
        used += cost
    if not chosen:
        held = len(entries)
        return "", (f"[playbook] 0/{len(entries)} entries injected; budget: "
                    f"{budget} words{env_note} — block omitted, {held} held")
    block = PB_HEADER + "\n" + "\n".join(chosen)
    b = "unlimited" if budget is None else f"{budget} words{env_note}"
    held = len(entries) - len(chosen)
    note = f" — {held} held (do not fit)" if held else ""
    return block, (f"[playbook] {len(chosen)}/{len(entries)} entries injected "
                   f"(~{used} words); budget: {b}{note}")


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
    if name == "playbook":
        def _playbook(task_prompt, fragments, *, job_text: str = "",
                      repo_map_text: str = "", budget=None, workdir="."):
            base = assemble_static(task_prompt, fragments, job_text=job_text,
                                   repo_map_text=repo_map_text)
            pb_text, _line = playbook_block_and_account(workdir, cfg)
            if pb_text:
                return (base + "\n\n" + pb_text) if base else pb_text
            return base

        return _playbook
    raise ValueError(
        f"unknown context strategy '{name}'. "
        f"Valid context strategies: {', '.join(VALID_CONTEXT)}"
    )
