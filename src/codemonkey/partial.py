"""Partial-application counter (loop 41, cycle 96 — R41 candidate C5).

Counts the failure mode BEFORE touching application semantics: no baseline,
no claim. Operates post-hoc over journal thread records (the same records
`journal.read_thread` returns), so historical runs are measurable without
re-running them.

Operational definitions (post-96F1/96F2 — stated plainly):
- A "hunk landed" = an edit-tool outcome (`write_file`, `edit_file`) with
  status `ok` or `replayed`, OR a shell outcome with status ok/replayed
  whose journaled (pre-redacted) command matches SHELL_PATTERNS.
- Identity is the filesystem path where evidenced (96F2: parsed from edit
  outputs and shell redirect targets); otherwise the record key. A file
  edited twice under two unparseable outputs still counts twice — the
  fallback proxy, flagged by the absence of a path.
- Shell outcomes with no `cmd` (all history pre-96F1) are DARK: counted in
  `dark_shell`, never classified. `summarize` states this scope in its own
  output.
- PARTIAL = ≥1 hunk landed AND an edit/shell-mutation outcome with status
  `error` at a later timestamp than the first landed hunk. The ordering
  requirement is the 91F1 lesson: a failure with nothing landed is
  ABORTED, not partial, and the report names WHICH key failed after WHICH
  landed key so the label is checkable against the evidence.
- Verifier outcome per thread is NOT in the journal (no verify tool
  records), so "tests pass by accident" is unmeasurable from history and is
  NOT claimed here — C97's plan object carries the verifier half.

Labels: NO_EDITS / SINGLE / CLEAN / PARTIAL / ABORTED.
"""

from __future__ import annotations

import re

EDIT_TOOLS = ("write_file", "edit_file")
LANDED = ("ok", "replayed")

# 96F1: shell-mediated mutation patterns over the journaled (pre-redacted)
# command text. Conservative by design: a missed exotic form undercounts,
# a quoted `>` overcounts — the cmd text is preserved so any classification
# is re-checkable. What is NOT here: chmod/chown (metadata, not content),
# mkdir (tree state, not content), bare `<<` heredoc without `>` (stdin).
SHELL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("sed -i", re.compile(r"\bsed\b[^|;&\n]*?\s(?:-i\b|--in-place\b)")),
    ("perl -i", re.compile(r"\bperl\b[^|;&\n]*?\s-i\b")),
    ("git apply", re.compile(r"\bgit\s+apply\b")),
    ("git checkout/restore/clean",
     re.compile(r"\bgit\s+(checkout|restore|clean)\b")),
    ("patch", re.compile(r"(?:^|[|&;`{(])\s*patch\b")),
    ("dd", re.compile(r"(?:^|[|&;`{(])\s*dd\b")),
    ("mv/cp/rm", re.compile(
        r"(?:^|[|&;`{(])\s*(mv|cp|rm|rmdir|unlink|shred|truncate|install)\b")),
    ("tee", re.compile(r"(?:^|[|&;])\s*tee\b")),
]
_REDIRECT_RE = re.compile(
    r"(?<!\d)(>>?\|?)\s*(?![&\s]*\d)(?!/dev/(?:null|stdout|stderr)\b)"
    r"([^\s;&|<>]+)")
_DEVNULL_RE = re.compile(r"^/dev/(?:null|stdout|stderr)$")


def shell_mutation(cmd: str) -> tuple[bool, str | None]:
    """(is_mutating, matched_pattern_name) for journaled shell text."""
    for pname, rx in SHELL_PATTERNS:
        if rx.search(cmd):
            return True, pname
    if _REDIRECT_RE.search(cmd):
        return True, "redirect"
    return False, None


def shell_targets(cmd: str) -> list[str]:
    """Redirect target paths from journaled shell text (96F2)."""
    return [m.group(2) for m in _REDIRECT_RE.finditer(cmd)
            if not _DEVNULL_RE.match(m.group(2))]


# 96F2: path extraction so distinct edits are exact, not arg-hash-proxied.
_WROTE_RE = re.compile(r"wrote \d+ bytes to (\S.*?)\s*$")
_EDIT_SINGLE_RE = re.compile(
    r"(?:applied \d+ block\(s\) to (.+?):|replaced .* in (.+?)\s*$|"
    r"replaced \d+ occurrence\(s\) in (.+?)\s*$)")
_EDIT_ATOMIC_RE = re.compile(r"^applied \d+ file\(s\) atomically:\n(.*)$", re.S)
_EDIT_ERR_RE = re.compile(r"error: edit \d+ \((.*?)\)")
_WRITEBACK_ERR_RE = re.compile(r"error: write-back failed: (.*)$")


def edit_paths(tool: str, output: str) -> list[str]:
    """Filesystem paths evidenced in an edit-tool outcome's output."""
    out = output or ""
    if tool == "write_file":
        m = _WROTE_RE.search(out)
        return [m.group(1)] if m else []
    if tool == "edit_file":
        paths: list[str] = []
        m = _EDIT_ATOMIC_RE.search(out)
        if m:
            for line in m.group(1).splitlines():
                line = line.strip()
                if line.endswith(": applied"):
                    paths.append(line[:-len(": applied")])
            return paths
        m = _EDIT_SINGLE_RE.search(out)
        if m:
            hit = next((g for g in m.groups() if g), None)
            return [hit] if hit else []
        m = _EDIT_ERR_RE.search(out)
        if m:
            return [m.group(1)]
        m = _WRITEBACK_ERR_RE.search(out)
        if m:
            return [seg.split(":")[0].strip()
                    for seg in m.group(1).split(";") if seg.strip()]
    return []


def _outcome_keys(tool: str, key: str, status: str, output: str,
                  cmd: str) -> list[tuple]:
    """Identity keys for one outcome record (96F2: paths where evidenced).

    Edit tools: parsed output paths when present, else the arg-hash key.
    Shell: redirect targets when present, else the record key — but ONLY for
    commands matching a mutation pattern; non-mutating shell returns [].
    """
    if tool in EDIT_TOOLS:
        paths = edit_paths(tool, output)
        if paths:
            return [("path", p) for p in paths]
        return [(tool, key)]
    if tool == "shell":
        mut, _ = shell_mutation(cmd or "")
        if not mut:
            return []
        targets = shell_targets(cmd or "")
        if targets:
            return [("shell-path", t) for t in targets]
        return [("shell", key)]
    return []


def classify_thread(records: list[dict]) -> dict:
    """Classify one thread's journal records. Pure function over evidence."""
    landed: dict[tuple, float] = {}
    failed: list[dict] = []
    dark_shell = 0  # 96F1: shell outcomes with no cmd — unobservable
    for r in records:
        if r.get("type") != "outcome":
            continue
        tool = r.get("tool", "")
        if tool not in EDIT_TOOLS and tool != "shell":
            continue
        if tool == "shell" and not r.get("cmd"):
            dark_shell += 1
            continue
        ts = r.get("ts", 0)
        keys = _outcome_keys(tool, r.get("key") or "", r.get("status", ""),
                             r.get("output", ""), r.get("cmd", ""))
        if not keys:
            continue
        if r.get("status") in LANDED:
            for k in keys:
                if k not in landed or ts < landed[k]:
                    landed[k] = ts
        elif r.get("status") == "error":
            for k in keys:
                failed.append({"key": k, "ts": ts,
                               "error_class": r.get("error_class")})
    landed_keys = sorted(landed, key=lambda k: landed[k])
    base: dict = {"dark_shell": dark_shell}
    if not landed_keys and not failed:
        base.update({"label": "NO_EDITS", "landed": [], "failed": []})
        return base
    if not landed_keys:
        base.update({"label": "ABORTED", "landed": [],
                     "failed": [(f["key"], f["error_class"]) for f in failed]})
        return base
    if len(landed_keys) == 1 and not failed:
        base.update({"label": "SINGLE", "landed": landed_keys, "failed": []})
        return base
    first_landed_ts = landed[landed_keys[0]]
    late_failures = [f for f in failed if f["ts"] > first_landed_ts]
    if late_failures:
        base.update({"label": "PARTIAL", "landed": landed_keys,
                     "failed": [(f["key"], f["error_class"])
                                for f in late_failures],
                     "first_landed": landed_keys[0]})
        return base
    if len(landed_keys) >= 2:
        base.update({"label": "CLEAN", "landed": landed_keys, "failed": []})
        return base
    base.update({"label": "SINGLE", "landed": landed_keys,
                 "failed": [(f["key"], f["error_class"]) for f in failed]})
    return base


def summarize(classified: dict[str, dict]) -> dict:
    """Baseline rate over per-thread classifications.

    The population is runs that ATTEMPTED >= 2 distinct edits (landed or
    failed) — a 1-landed + 1-failed run is partial application, and a
    landed-only gate would drop exactly the failure mode being counted.
    Single-edit and no-edit threads are reported, never folded in.
    """
    multi = {t: c for t, c in classified.items()
             if len(set(c["landed"]) | {k for k, _ in c["failed"]}) >= 2}
    partial = {t: c for t, c in multi.items() if c["label"] == "PARTIAL"}
    # No multi-edit runs → no rate exists. 0.0 would claim a measured
    # absence; None states the denominator is zero.
    rate = (len(partial) / len(multi)) if multi else None
    dark = sum(c.get("dark_shell", 0) for c in classified.values())
    # 96F1: the scope limit lives in the output itself, not only in a
    # docstring — a reader of this dict must see what it cannot count.
    scope = ("counts write_file/edit_file outcomes plus shell outcomes "
             "carrying cmd (post-96F1 pre-redacted command text); "
             f"{dark} shell outcomes predate cmd capture and are "
             "unobservable; shell mutation is pattern-matched "
             "(conservative list in partial.SHELL_PATTERNS) over preserved "
             "cmd text and is re-checkable per record.")
    return {
        "threads": len(classified),
        "with_edits": sum(1 for c in classified.values() if c["landed"]),
        "multi_edit": len(multi),
        "partial": len(partial),
        "partial_threads": sorted(partial),
        "rate": rate,
        "dark_shell": dark,
        "scope": scope,
        "labels": {t: c["label"] for t, c in classified.items()},
    }
