"""loop47 cycle 108 — the reflector: journal records → evidence-cited deltas.

What these pin, beyond "it returns something":

* GROUPING: two failures of the same (tool, category) become ONE delta whose
  `evidence` cites BOTH record indexes — the citation is the point (a claim
  without its evidence is the defect class this arc fights);
* DETERMINISM: same records, byte-identical deltas; no store access at all
  (reflection must be free of side effects — merge is the only verb that
  writes);
* HONEST UNMAPPED: transient-infrastructure and uncoded failures yield NO
  candidate (a delta that says "something failed" teaches nothing), so an
  all-transient thread reflects to `[]`, exit 0;
* TAINT POSTURE (coarse, loop 49 refines): a group fed by a source tool
  (shell stdout / web_fetch) is `taint_free: False` even though the delta's
  text is always a template — the flag describes the EVIDENCE lineage.
"""

from __future__ import annotations

import json

from codemonkey import playbook


def _outcome(tool, status="error", error_class="tool-error", output="",
             key="k"):
    return {"type": "outcome", "tool": tool, "key": key, "status": status,
            "error_class": error_class, "output": output}


RECS = [
    _outcome("shell", output="bash: xyzzy: command not found", key="t1"),
    _outcome("shell", output="bash: xyzzy: command not found", key="t2"),
    _outcome("write_file", error_class="schema_mismatch", output="bad args",
             key="t3"),
    _outcome("shell", status="ok", error_class="", output="done", key="t4"),
    {"type": "event", "tool": "", "key": ""},
    _outcome("shell", error_class="timeout", output="timed out", key="t5"),
]


def test_grouping_evidence_and_determinism():
    deltas = playbook.reflect(RECS, thread="t-demo")
    assert len(deltas) == 2  # shell/wrong-tool and write_file/wrong-argument
    shell = [d for d in deltas if d["kind"] == "pitfall"
             and d["text"].startswith("shell")][0]
    wf = [d for d in deltas if d["text"].startswith("write_file")][0]
    assert shell["evidence"] == [0, 1]
    assert "wrong-tool" in shell["text"] and "2 occurrence" in shell["text"]
    assert wf["evidence"] == [2]
    assert "wrong-argument" in wf["text"]
    assert deltas == playbook.reflect(RECS, thread="t-demo")  # byte-identical


def test_transient_and_uncoded_failures_yield_no_candidate():
    recs = [
        _outcome("shell", error_class="timeout", output="timed out"),
        _outcome("shell", error_class="transport", output="connection refused"),
        _outcome("shell", error_class="tool-error", output="mystery"),
    ]
    assert playbook.reflect(recs, thread="t") == []


def test_taint_posture_is_per_group_and_conservative():
    deltas = playbook.reflect(RECS, thread="t-demo")
    shell = [d for d in deltas if d["text"].startswith("shell")][0]
    wf = [d for d in deltas if d["text"].startswith("write_file")][0]
    assert shell["provenance"]["taint_free"] is False   # shell stdout source
    assert wf["provenance"]["taint_free"] is True       # not a source tool


def test_reflection_writes_nothing(tmp_path):
    before = sorted(p.name for p in tmp_path.iterdir())
    playbook.reflect(RECS, thread="t-demo")
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert not playbook.store_path(tmp_path).exists()


def test_reflected_deltas_merge_with_evidence_preserved(tmp_path):
    deltas = playbook.reflect(RECS, thread="t-demo")
    rep = playbook.merge_deltas(tmp_path, deltas)
    assert rep["added"] == 2 and rep["refused"] == []
    entries = playbook.list_entries(tmp_path)
    shell = [e for e in entries if e["text"].startswith("shell")][0]
    assert shell["evidence"] == [0, 1]
    assert shell["status"] == "quarantined"
    assert shell["provenance"]["source"] == "reflect:t-demo"
    assert playbook.load_admitted(tmp_path) == []


def test_evidence_survives_reserialization_and_bad_evidence_refused(tmp_path):
    playbook.merge_deltas(tmp_path, [{
        "kind": "pitfall", "section": "failures", "text": "x → y: z",
        "evidence": [3, 1, 2],
        "provenance": {"run_id": "r", "session_id": "", "taint_free": True},
    }])
    e = playbook.list_entries(tmp_path)[0]
    assert e["evidence"] == [1, 2, 3]  # normalized sorted
    raw = json.loads(playbook.store_path(tmp_path).read_text())
    assert raw["entries"][0]["evidence"] == [1, 2, 3]  # on disk, too
    rep = playbook.merge_deltas(tmp_path, [{
        "kind": "pitfall", "section": "failures", "text": "q",
        "evidence": ["zero"], "provenance": {"run_id": "r", "session_id": "",
                                             "taint_free": True}}])
    assert rep["refused"] and "evidence" in rep["refused"][0]["reason"]
