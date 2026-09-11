"""C106 — the register's completeness claim, CHECKED instead of asserted.

`build/CAPABILITY_REGISTER.md` opens with "One row per module in
`src/codemonkey/`" and "No UNVALIDATED rows". Both were true when written
(loop 38, cycle 81) and nothing re-checked either one. An audit on 2026-09-10
found **12 modules with no row at all** — every module loops 39-45 added —
while the file's opening sentence went on claiming coverage.

That is the defect class this arc keeps finding in a new place: a document
making a claim with no control behind it (102F8 was the same defect in
`contract.md` §2). These tests are the control.

The scope matters: the deletion-verdict table below the active table
legitimately names modules that no longer exist — that IS the R-A verdict.
Only ACTIVE rows are checked for existence.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "build" / "register_audit.py"
REGISTER = ROOT / "build" / "CAPABILITY_REGISTER.md"


def _audit():
    spec = importlib.util.spec_from_file_location("register_audit", AUDIT)
    assert spec and spec.loader, "cannot load the register audit"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_module_has_an_active_row():
    a = _audit()
    rows = a.register_rows(REGISTER.read_text())
    missing = [m for m in a.module_names() if m not in rows]
    assert not missing, (
        f"modules in src/codemonkey/ with no ACTIVE register row: {missing} — "
        f"a new module is either PROVEN-LIVE with its entry probe, UNIT-ONLY "
        f"with its reason, or it belongs in the deletion table")


def test_no_active_row_names_a_module_that_does_not_exist():
    a = _audit()
    rows = a.register_rows(REGISTER.read_text())
    stale = sorted(set(rows) - set(a.module_names()))
    assert not stale, (
        f"ACTIVE rows for modules that no longer exist: {stale} — a deleted "
        f"module's verdict belongs in the deletion table, not the active one")


def test_no_row_is_unvalidated():
    """The register's other opening claim: every row is PROVEN-LIVE,
    UNIT-ONLY with a reason, or DEAD."""
    text = REGISTER.read_text()
    assert "| UNVALIDATED" not in text


def test_every_row_carries_a_status():
    """A row without a status is neither proven nor excused."""
    a = _audit()
    rows = a.register_rows(REGISTER.read_text())
    for name, row in rows.items():
        assert any(s in row for s in ("PROVEN-LIVE", "UNIT-ONLY", "DEAD")), \
            f"{name}: row carries no status"
