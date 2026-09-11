"""C106 audit: does CAPABILITY_REGISTER.md cover every module that exists?

The register claims "one row per module in `src/codemonkey/`" and that claim
was true when it was written (loop 38, cycle 81). Loops 39-45 added modules.
A register that says "no UNVALIDATED rows" while silently omitting modules is
the same defect class as a documented type that no run can produce: the
document's completeness is asserted and never checked.

Usage:  uv run python build/register_audit.py [--missing] [--triples]

`--triples` re-derives the loops-38..45 module set from git and checks the
register's R-G / R-F annotation table against it (both directions, floored).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTER = ROOT / "build" / "CAPABILITY_REGISTER.md"
SRC = ROOT / "src" / "codemonkey"


def module_names() -> list[str]:
    """Every module that should have a row: src/codemonkey/*.py plus
    `__init__` (the register counts it, and it carries a real row)."""
    return sorted(p.stem for p in SRC.glob("*.py"))


_HEADER_CELLS = {"module", "status", "entry probe", "note"}


def register_rows(text: str) -> dict[str, str]:
    """module -> the whole row, for ACTIVE rows only.

    Scoped to the "## Active modules" section: the deletion-verdict table
    below legitimately names modules that no longer exist (that is the R-A
    verdict), and counting those as active rows would report the register's
    own bookkeeping as drift. Table headers are skipped too — the first cell
    of a header is `module`, which would otherwise read as a row for a module
    that never existed.
    """
    active = text.split("## Active modules", 1)[-1].split("\n## ", 1)[0]
    rows: dict[str, str] = {}
    for line in active.splitlines():
        m = re.match(r"^\|\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|\s*(\S+)", line)
        if m and m.group(1) not in _HEADER_CELLS:
            rows[m.group(1)] = line
    return rows


# --- R-G / R-F annotations (loop45-final) ---------------------------------
#
# The v4.0 acceptance terms require every loop-38..44 row to carry its
# LOCAL / PUBLISHED / GAP triple (R-G) and its cost (R-F). "Every" needs a
# control, and a control that iterates a hand-maintained copy of the module
# set asserts nothing about which modules the arc actually added — so the set
# is DERIVED from git: every top-level module whose first commit descends
# from the R38 research commit (`ARC_BOUNDARY`, the first commit of the
# loops-38..45 arc). The tip is pinned to the v4.0.0 tag once it exists, so
# modules added by LATER arcs do not drift into a clause about this one.

ARC_BOUNDARY = "2575515"  # CYCLE R38 — first commit of the loops 38-45 arc
ANNOTATION_HEADING = "## R-G / R-F annotations"
ANNOTATION_FLOOR = 13  # 12 modules (C106) + branches_cli (loop38); floor, not a target


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout


def arc_tip() -> str:
    """The arc's closing tip: the v4.0.0 tag when it exists, else HEAD
    (during the close cycle itself the tag does not exist yet)."""
    try:
        return _git("rev-parse", "--verify", "v4.0.0^{commit}").strip()
    except subprocess.CalledProcessError:
        return "HEAD"


def arc_first_adds() -> dict[str, str]:
    """module -> its OLDEST first-add commit, from ONE git pass."""
    out = _git("log", "--diff-filter=A", "--name-only", "--format=@%H",
               "--", "src/codemonkey")
    first: dict[str, str] = {}
    cur = ""
    for line in out.splitlines():
        if line.startswith("@"):
            cur = line[1:].strip()
        else:
            p = line.strip()
            if p.startswith("src/codemonkey/") and p.count("/") == 2 \
                    and p.endswith(".py"):
                first[p.rsplit("/", 1)[-1][:-3]] = cur  # newest->oldest: ends oldest
    return first


def arc_modules() -> list[str]:
    """Top-level modules whose first commit descends from ARC_BOUNDARY and is
    not past the v4.0.0 tip."""
    first = arc_first_adds()
    desc = set(_git("rev-list", f"{ARC_BOUNDARY}..{arc_tip()}").split())
    return sorted(m for m, h in first.items() if h in desc)


def annotation_rows(text: str) -> dict[str, list[str]]:
    """module -> [module cell, LOCAL, PUBLISHED, GAP, COST] from the
    R-G / R-F table, scoped to its own section so unrelated tables below
    cannot satisfy or pollute the check."""
    sect = text.split(ANNOTATION_HEADING, 1)[-1].split("\n## ", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in sect.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 5 or cells[0].startswith("module") or set(cells[0]) <= set("- "):
            continue
        rows[cells[0].split(" (", 1)[0].strip()] = cells
    return rows


def triples_report() -> int:
    """audit --triples: re-derive the arc set and check the annotation table
    against it, both directions, with a floor so a broken derivation cannot
    read as 'all covered'."""
    derived = arc_modules()
    rows = annotation_rows(REGISTER.read_text())
    missing = sorted(set(derived) - set(rows))
    extra = sorted(set(rows) - set(derived))
    incomplete = {name: i for name in derived if name in rows
                  for i, c in [(i, c) for i, c in enumerate(rows[name][1:], 1)]
                  if not c or c == "-"}
    print(f"arc modules derived from git ({ARC_BOUNDARY}..{arc_tip()[:8]}): {len(derived)}")
    for m in derived:
        print(f"  {'OK ' if m in rows else 'MISSING'} {m}")
    if len(derived) < ANNOTATION_FLOOR:
        print(f"FLOOR BREACH: derived {len(derived)} < floor {ANNOTATION_FLOOR} — "
              f"the derivation itself is suspect; do not read anything as covered")
        return 1
    if missing:
        print(f"ARC MODULES WITH NO ANNOTATION ROW ({len(missing)}): {missing}")
    if extra:
        print(f"ANNOTATION ROWS FOR MODULES OUTSIDE THE ARC ({len(extra)}): {extra}")
    if incomplete:
        print(f"ROWS WITH EMPTY R-G/R-F CELLS: {incomplete}")
    return 1 if (missing or extra or incomplete) else 0


def main() -> int:
    if "--triples" in sys.argv:
        return triples_report()
    text = REGISTER.read_text()
    rows = register_rows(text)
    mods = module_names()
    missing = [m for m in mods if m not in rows]
    statuses: dict[str, int] = {}
    for line in rows.values():
        m = re.search(r"\|\s*(PROVEN-LIVE|UNIT-ONLY|DEAD|UNVALIDATED)", line)
        if m:
            statuses[m.group(1)] = statuses.get(m.group(1), 0) + 1

    print(f"modules in src/: {len(mods)}")
    print(f"register rows:   {len(rows)}")
    print(f"statuses:        {statuses}")
    if missing:
        print(f"\nMODULES WITH NO REGISTER ROW ({len(missing)}):")
        for m in missing:
            print(f"  - {m}")
    extra = sorted(set(rows) - set(mods))
    if extra:
        print(f"\nREGISTER ROWS FOR MODULES THAT NO LONGER EXIST ({len(extra)}):")
        for m in extra:
            print(f"  - {m}")
    if "--missing" in sys.argv:
        return 1 if missing else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
