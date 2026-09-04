"""Honest-completion gate (loop17, cycle 52).

Fizzbuzz-class defect: the agent SAID it wrote tests / ran commands and
didn't. Outcome-based verification (reinventing.ai 2026-04): check the final
reply's action claims against OBSERVABLE evidence — the execution journal and
the filesystem — not against the model's self-report.

Off by default; enabled per exec run via verify_claims=True.

A claim is matched in the reply text with patterns like:
  "created/wrote X", "ran the tests / tests pass / pytest passed"
Evidence looked up:
  - file claims  → the path exists (relative to workdir) OR the journal has a
    write_file intent whose args hash touched a path with that basename
  - command claims → the journal has a shell intent with status ok whose
    args/text overlaps the command fragment
Any unmatched claim → [UNVERIFIED: <claim>] marker appended to the reply and
an unverified_claim outcome journaled.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# claims: file operations the reply asserts happened
_FILE_CLAIM = re.compile(
    r"\b(?:created|wrote|saved|generated|updated)\s+(?:the\s+)?(?:file\s+)?"
    r"`?([\w./-]+\.\w{1,4})`?", re.I)
# claims: commands/tests the reply asserts ran successfully
_CMD_CLAIM = re.compile(
    r"\b(?:ran|executed)\s+(?:the\s+)?(?:command\s+)?[`\"']?(?P<cmd>[\w./-][^`\n\"']{0,60})[`\"']?"
    r"|(?P<testpass>\b(?:tests?|pytest|suite)\s+(?:pass(?:ed|ing)?|green|all passed))", re.I)


def _journal_records(thread_id: str) -> list[dict]:
    from .journal import read_thread

    try:
        return read_thread(thread_id)
    except Exception:
        return []


def check_claims(reply: str, *, workdir, thread_id: str) -> dict:
    """Audit action claims in reply against journal + filesystem.
    Returns {claims: [...], unverified: [...], verified: [...]}."""
    records = _journal_records(thread_id)
    result = {"claims": [], "unverified": [], "verified": []}

    # file claims
    for m in _FILE_CLAIM.finditer(reply):
        path = m.group(1)
        result["claims"].append({"kind": "file", "target": path})
        exists = (workdir / path).is_file() if not os.path.isabs(path) else os.path.isfile(path)
        if exists:
            result["verified"].append(result["claims"][-1])
        else:
            result["unverified"].append(result["claims"][-1])

    # command claims: only when the claim asserts success (ran/tests pass)
    for m in _CMD_CLAIM.finditer(reply):
        explicit = m.group("cmd")
        if explicit:
            frag = explicit.strip("` ").strip()
            # only if the surrounding sentence actually asserts success
            start, end = m.span()
            window = reply[max(0, end - 10):end + 40].lower()
            if not any(w in window for w in ("pass", "success", "ok", "green", "worked")):
                continue
        else:
            # "tests pass" style: success words are the whole claim
            frag = m.group("testpass")
        claim = {"kind": "command", "target": frag[:60]}
        result["claims"].append(claim)
        ok = any(
            rec.get("tool") == "shell" and rec.get("status") == "ok"
            and any(tok in str(rec.get("output", "")) + str(rec.get("key", ""))
                    for tok in _tokens(frag) + ["passed", "pass", "ok"])
            for rec in records)
        if ok:
            result["verified"].append(claim)
        else:
            result["unverified"].append(claim)
    return result


def _tokens(fragment: str) -> list[str]:
    return [w for w in fragment.split() if len(w) >= 4]


def annotate(reply: str, *, workdir, thread_id: str) -> tuple[str, dict]:
    """Run check_claims; if any unverified, append markers to the reply."""
    res = check_claims(reply, workdir=workdir, thread_id=thread_id)
    if res["unverified"]:
        markers = ", ".join(
            f"[UNVERIFIED: {c['kind']} '{c['target']}']" for c in res["unverified"])
        reply = reply.rstrip() + "\n\n" + markers
        try:
            from .journal import record

            record(thread_id, "outcome", tool="verify_claims", key=thread_id,
                   status="flagged",
                   output=f"unverified: {res['unverified']}")
        except OSError:
            pass
    return reply, res


