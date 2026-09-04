"""R34: corrections compiled into enforcement."""

from __future__ import annotations

from codemonkey.compile_rules import compile_corrections, merge_rules


CLASSES = {("shell", "timeout"): 3, ("edit_file", "schema_mismatch"): 2,
           ("shell", "ok"): 9, ("route", "timeout"): 5}


def test_over_threshold_compile():
    drafts = compile_corrections(CLASSES)
    tools = {(d["tool"], d["action"]) for d in drafts}
    assert ("shell", "ask") in tools and ("edit_file", "ask") in tools
    assert all(d["action"] == "ask" for d in drafts)


def test_under_threshold_skipped():
    drafts = compile_corrections({("shell", "timeout"): 1}, threshold=2)
    assert drafts == []


def test_infra_tools_skipped():
    drafts = compile_corrections(CLASSES)
    assert not any(d["tool"] == "route" for d in drafts)


def test_already_covered_skipped():
    existing = [{"tool": "shell", "pattern": "*", "action": "deny"}]
    drafts = compile_corrections(CLASSES, existing_rules=existing)
    assert not any(d["tool"] == "shell" for d in drafts)


def test_merge_dedupes():
    current = [{"tool": "shell", "pattern": "*", "action": "ask"}]
    drafts = [{"tool": "shell", "pattern": "*", "action": "ask"},
              {"tool": "edit_file", "pattern": "*", "action": "ask"}]
    merged = merge_rules(current, drafts)
    assert len(merged) == 2
    assert merged[-1]["tool"] == "edit_file"
