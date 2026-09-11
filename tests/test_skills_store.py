"""loop46 cycle 82 — the skill store: quarantine, provenance, and what earns
its way out of it.

The load-bearing properties tested here are R-J's: a candidate the agent
writes starts quarantined and is NOT loadable; promotion is a status a gate
must set, never a default; provenance is structured and mandatory (the taint
rule in cycle 85 must be able to refuse contaminated lineage later); and the
store is uncommittable by default. The negative cases (schema rejection,
builtin collision, admitted-skill overwrite) are the discriminating ones — a
store that accepts everything is the same defect class as a gate that never
fires.
"""

from __future__ import annotations

import json

import pytest

from codemonkey import skills


def _manifest(name: str = "demo_skill", **over) -> dict:
    man = {
        "name": name,
        "spec": "one-line description of what this skill does",
        "params": {"type": "object", "properties": {}},
        "probe": "echo ok",
        "provenance": {"run_id": "run-123", "session_id": "th-abc",
                       "taint_free": True},
        "status": "quarantined",
    }
    man.update(over)
    return man


def test_manifest_round_trip(tmp_path):
    path = skills.write_manifest(tmp_path, _manifest("demo_roundtrip"),
                                 tool_src="def run(args, ctx):\n    pass\n")
    assert path.is_file()
    assert (tmp_path / skills.STORE_DIR / "demo_roundtrip" / "tool.py").is_file()
    man = skills.read_manifest(tmp_path, "demo_roundtrip")
    assert man["name"] == "demo_roundtrip"
    assert man["status"] == "quarantined"
    assert man["probe"] == "echo ok"
    assert man["provenance"]["run_id"] == "run-123"
    assert man["provenance"]["taint_free"] is True
    assert isinstance(man.get("history"), list)
    assert man.get("created")


@pytest.mark.parametrize("bad", [
    {"params": {"type": "string", "properties": {}}},   # wrong schema type
    {"params": {"type": "object"}},                      # properties missing
    {"params": "not a dict"},                            # not a schema at all
    {"name": "Bad-Name!"},                               # invalid name
    {"status": "blessed"},                               # unknown status
    {"spec": "  "},                                      # empty spec
])
def test_manifest_schema_rejection(tmp_path, bad):
    with pytest.raises(skills.SkillError):
        skills.write_manifest(tmp_path, _manifest(**bad))
    # a refused manifest must not leave anything loadable behind
    assert skills.list_skills(tmp_path) == []


def test_provenance_is_required_and_structured(tmp_path):
    with pytest.raises(skills.SkillError, match="provenance"):
        skills.write_manifest(tmp_path, _manifest(provenance=None))
    man = _manifest()
    del man["provenance"]["taint_free"]
    with pytest.raises(skills.SkillError, match="taint_free"):
        skills.write_manifest(tmp_path, man)
    man = _manifest()
    man["provenance"]["taint_free"] = "yes"          # a string is a claim, not a fact
    with pytest.raises(skills.SkillError, match="boolean"):
        skills.write_manifest(tmp_path, man)
    assert skills.list_skills(tmp_path) == []


def test_status_transitions_are_recorded_in_history(tmp_path):
    skills.write_manifest(tmp_path, _manifest("demo_moves"))
    man = skills.set_status(tmp_path, "demo_moves", "admitted", reason="C83 gate")
    assert man["status"] == "admitted"
    assert len(skills.load_admitted(tmp_path)) == 1
    man = skills.set_status(tmp_path, "demo_moves", "evicted", reason="probe failed later")
    assert man["status"] == "evicted"
    history = man["history"]
    assert [(h["from"], h["to"]) for h in history] == \
        [("quarantined", "admitted"), ("admitted", "evicted")]
    assert "C83 gate" in history[0]["reason"]
    # eviction removes it from the loaded set (R-A)
    assert skills.load_admitted(tmp_path) == []
    with pytest.raises(skills.SkillError):
        skills.set_status(tmp_path, "demo_moves", "blessed")


def test_no_store_is_honest_empty_not_an_error(tmp_path):
    root = skills.store_root(tmp_path)
    assert not root.exists()
    assert skills.list_skills(tmp_path) == []
    assert skills.load_admitted(tmp_path) == []
    # a run with skills=use against a repo that never had a store must not die
    assert skills.store_root(tmp_path) == tmp_path / ".codemonkey" / "skills"


def test_builtin_name_collision_is_rejected(tmp_path):
    for builtin in ("shell", "read_file", "graph_query"):
        with pytest.raises(skills.SkillError, match="built-in"):
            skills.write_manifest(tmp_path, _manifest(builtin))
    assert skills.list_skills(tmp_path) == []


def test_quarantined_skills_are_not_loaded(tmp_path):
    skills.write_manifest(tmp_path, _manifest("demo_q"))
    rows = skills.list_skills(tmp_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "quarantined"
    assert skills.load_admitted(tmp_path) == []      # the whole point of quarantine


def test_store_is_gitignored_by_default_and_idempotent(tmp_path):
    skills.write_manifest(tmp_path, _manifest("demo_ignore"))
    gi = (tmp_path / ".gitignore").read_text()
    assert f"{skills.STORE_DIR}/" in gi
    first = gi
    skills.write_manifest(tmp_path, _manifest("demo_ignore2"))
    assert (tmp_path / ".gitignore").read_text() == first  # no duplicate line


def test_admitted_skill_cannot_be_clobbered(tmp_path):
    skills.write_manifest(tmp_path, _manifest("demo_lock"),
                          tool_src="# v1\n")
    skills.set_status(tmp_path, "demo_lock", "admitted", reason="gate")
    with pytest.raises(skills.SkillError, match="refusing to overwrite"):
        skills.write_manifest(tmp_path, _manifest("demo_lock"),
                              tool_src="# sneaky replacement\n")
    assert (tmp_path / skills.STORE_DIR / "demo_lock" / "tool.py").read_text() \
        == "# v1\n"


def test_invalid_manifest_on_disk_is_surfaced_not_hidden(tmp_path):
    d = tmp_path / skills.STORE_DIR / "demo_broken"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({"name": "demo_broken"}))
    rows = skills.list_skills(tmp_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "invalid"
    assert "missing required field" in rows[0]["invalid_reason"]
    assert skills.load_admitted(tmp_path) == []
