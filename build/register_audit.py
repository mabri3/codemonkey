"""C106 audit: does CAPABILITY_REGISTER.md cover every module that exists?

The register claims "one row per module in `src/codemonkey/`" and that claim
was true when it was written (loop 38, cycle 81). Loops 39-45 added modules.
A register that says "no UNVALIDATED rows" while silently omitting modules is
the same defect class as a documented type that no run can produce: the
document's completeness is asserted and never checked.

Usage:  uv run python build/register_audit.py [--missing]
"""

from __future__ import annotations

import re
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


def main() -> int:
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
