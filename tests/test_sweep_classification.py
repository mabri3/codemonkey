"""102F10 — the sweep classification is a CLAIM; this is its control.

A row may be marked green only with a run behind it. That is not checkable by
reading `sweep-classification.md` — the markdown is the claim. These tests go
back to the artifacts: every green row must cite an evidence log that exists
and contains the output its own assertion produced, and every row must mirror
a body that is still in `build/acceptance_sweep.sh`, so a row cannot be
reclassified here while the sweep has moved on.

Break-verified the 102F1 way: delete `build/acceptance_outputs/sweep-A7.log`
(the artifact, not a stand-in the test builds) and
`test_every_green_row_cites_evidence_that_exists` goes RED. See BUILD_LOG.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLASS_JSON = ROOT / "build" / "sweep-classification.json"
SWEEP = ROOT / "build" / "acceptance_sweep.sh"
DRIVER = ROOT / "build" / "sweep_endpoint_gated.py"

# What each row's green has to have PRODUCED. `stdout`/`stderr` are the
# captured streams of the binary run; `log` is the whole evidence file.
MARKERS: dict[str, list[tuple[str, str]]] = {
    "A4": [("stdout", "stub-model")],
    "A5": [("stdout", "pong")],
    "A6": [("stdout", "thread.started")],
    "A7": [("stdout", "banana")],
    "A9": [("stdout", "codemonkey_tool_test"), ("stderr", "[exit 0]")],
    "A10": [("stdout", "project_name")],
    "A11": [("stdout", "zebra")],
    "A12": [("log", "sessions"), ("log", "thread-in-listing=True")],
    "A16": [("stdout", "verdict")],
}


def doc() -> dict:
    return json.loads(CLASS_JSON.read_text())


def _section(log_text: str, which: str) -> str:
    """ALL `--- which ---` blocks, concatenated.

    A row may back its verdict with several runs (A11 resumes, then lists
    sessions; A12 lists). Reading only the first block made A11's green look
    unsupported — the control caught its own parser, which is the point.
    """
    marker = f"--- {which} ---"
    parts: list[str] = []
    idx = 0
    while True:
        start = log_text.find(marker, idx)
        if start < 0:
            return "\n".join(parts)
        start += len(marker)
        end = log_text.find("--- ", start)
        parts.append(log_text[start:end if end > 0 else len(log_text)])
        idx = start


def problems() -> list[str]:
    """Every way the committed classification could be lying. Empty == honest."""
    out: list[str] = []
    d = doc()
    rows = {r["row"]: r for r in d["rows"]}

    for name, markers in MARKERS.items():
        if name not in rows:
            out.append(f"{name}: classified row is missing entirely")
            continue
        r = rows[name]
        if r["status"] != "PASS":
            continue                      # a red row claims nothing
        ev = ROOT / r.get("evidence", "")
        if not r.get("evidence") or not ev.exists():
            out.append(f"{name}: marked PASS but its evidence log is missing "
                       f"({r.get('evidence')!r}) — green with no run behind it")
            continue
        text = ev.read_text()
        for where, needle in markers:
            hay = text if where == "log" else _section(text, where)
            if needle not in hay:
                out.append(f"{name}: marked PASS but {where} does not contain "
                           f"{needle!r} — the run behind the green does not "
                           f"show the thing the row asserts")

    for r in d["rows"]:
        if r["green_is_full"] and r["residual_model_clause"]:
            out.append(f"{r['row']}: marked fully green but still carries a "
                       f"model-clause residual")

    counts = d["counts"]
    measured = {
        "blocked_rows_classified": len(d["rows"]),
        "green_with_run_behind_it": len([r for r in d["rows"] if r["status"] == "PASS"]),
        "green_with_no_model_clause": len([r for r in d["rows"] if r["green_is_full"]]),
        "red": len([r for r in d["rows"] if r["status"] != "PASS"]),
    }
    for k, v in measured.items():
        if counts.get(k) != v:
            out.append(f"counts[{k}]={counts.get(k)!r} but the rows say {v}")
    if counts.get("green_with_no_model_clause", 0) + \
            counts.get("green_with_named_residual", 0) != measured["green_with_run_behind_it"]:
        out.append("green rows do not decompose into full-green + residual")
    return out


def test_every_green_row_cites_evidence_that_exists():
    assert not problems(), "classification is not backed by its artifacts:\n" + \
        "\n".join(problems())


def test_rows_mirror_a_body_that_is_still_in_the_sweep():
    sweep = SWEEP.read_text()
    missing = [r["row"] for r in doc()["rows"] if r["sweep_mirror"] not in sweep]
    assert not missing, (
        f"rows {missing} claim to stand in for sweep bodies that no longer "
        f"contain their distinguishing text — the classification has drifted "
        f"from the thing it classifies")


def test_driver_and_committed_classification_agree_on_the_row_set():
    spec = importlib.util.spec_from_file_location("sweep_driver", DRIVER)
    assert spec and spec.loader, "cannot load the sweep driver"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert sorted(s["row"] for s in mod.ROW_SPECS) == \
        sorted(r["row"] for r in doc()["rows"]), \
        "the driver and the committed classification disagree about which rows exist"


def test_no_row_is_waived_as_a_class():
    """A blanket waiver is not an exception list: each entry names one clause."""
    d = doc()
    for e in d["exception_list"]:
        assert e["waived_clause"].strip(), f"{e['row']}: empty waived clause"
        assert len(e["waived_clause"]) > 40, \
            f"{e['row']}: waived clause is not specific enough to be a waiver"
        assert e["row"] in {r["row"] for r in d["rows"]}


def test_marker_table_covers_every_classified_row():
    """A new row with no markers would silently pass the evidence check."""
    assert sorted(MARKERS) == sorted(r["row"] for r in doc()["rows"]), \
        "MARKERS and the classified rows disagree — a row would go unchecked"


@pytest.mark.parametrize("row", sorted(MARKERS))
def test_evidence_log_records_the_binary_and_the_assertion_it_mirrors(row):
    r = next(x for x in doc()["rows"] if x["row"] == row)
    text = (ROOT / r["evidence"]).read_text()
    assert "# binary:" in text and "codemonkey" in text
    assert f"assertion mirrors acceptance_sweep.sh: {r['sweep_mirror']!r}" in text
