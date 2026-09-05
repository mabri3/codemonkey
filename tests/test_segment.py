"""Cycles 99 (ladder + malformed metric) + 100 (segmentation ON/OFF).

The endpoint is down, so live numbers are BLOCKED — what is proven here is
the measurement plumbing, with scripted providers standing in for the
capability tiers: a good provider clears all tiers with zero malformed; a
provider emitting schema-violating calls fails L1 WITH the malformed count
to show for it. The ladder is provider-agnostic: same runner, live numbers
when the endpoint returns.
"""

from __future__ import annotations

import json

from codemonkey.ladder import TIERS, run_ladder, run_segmented


class _Turn:
    def __init__(self, content):
        self.content = content
        self.reasoning = ""
        self.usage = {"total_tokens": 10}
        self.tool_calls = []


def _tool(name, args):
    return _Turn("TOOL_CALL: " + json.dumps({"name": name, "arguments": args}) + "\n")


class _GoodProv:
    """Base: per-turn counter. Subclasses script one tier each."""
    protocol = "prompt"

    def __init__(self):
        self.turns = 0

    def close(self):
        pass


class _L1Prov(_GoodProv):
    def chat(self, messages, system=None, **kw):
        self.turns += 1
        if self.turns == 1:
            return _tool("write_file", {"path": "answer.txt", "content": "42"})
        return _Turn("done")


class _L2Prov(_GoodProv):
    def chat(self, messages, system=None, **kw):
        self.turns += 1
        if self.turns <= 3:
            c = "abc"[self.turns - 1]
            return _tool("write_file", {"path": f"{c}.txt", "content": c})
        return _Turn("done")


class _L3Prov(_GoodProv):
    def chat(self, messages, system=None, **kw):
        self.turns += 1
        if self.turns == 1:
            return _tool("read_file", {"path": "in.txt"})
        if self.turns == 2:
            return _tool("write_file", {"path": "out.txt", "content": "42"})
        return _Turn("done")


class _BadProv:
    """Schema-violating calls: missing required path arg."""
    protocol = "prompt"

    def chat(self, messages, system=None, **kw):
        return _tool("write_file", {"content": "x"})

    def close(self):
        pass


class _RouterProv:
    """Dispatches per-tier providers, routed fresh every call by the tier
    prompt markers in history (no latching — tiers share one instance)."""
    protocol = "prompt"

    def __init__(self):
        self.subs = {}

    def chat(self, messages, system=None, **kw):
        hist = json.dumps(messages)
        if "42 (just 42)" in hist:
            key, cls = "L1", _L1Prov
        elif "a.txt" in hist:
            key, cls = "L2", _L2Prov
        else:
            key, cls = "L3", _L3Prov
        if key not in self.subs:
            self.subs[key] = cls()
        return self.subs[key].chat(messages, system, **kw)

    def close(self):
        pass


def test_ladder_tiers_defined():
    assert [t["id"] for t in TIERS] == ["L1", "L2", "L3"]
    assert all(callable(t["check"]) for t in TIERS)


def test_good_provider_clears_ladder_no_malformed(tmp_path):
    res = run_ladder(_RouterProv(), tmp_path, needles=[])
    assert res["cleared"] == "3/3", res
    assert res["total_malformed"] == 0
    assert all(t["pass"] for t in res["tiers"].values())


def test_bad_provider_fails_l1_with_malformed_count(tmp_path):
    res = run_ladder(_BadProv(), tmp_path, needles=[])
    assert res["tiers"]["L1"]["pass"] is False
    assert res["tiers"]["L1"]["malformed"] >= 1
    assert res["total_malformed"] >= 1


def test_eval_counts_malformed_per_task(tmp_path):
    import yaml

    from codemonkey.eval import run_suite

    suite = tmp_path / "suite.yaml"
    suite.write_text(yaml.safe_dump({
        "name": "m",
        "tasks": [{"id": "t1", "prompt": "x", "expect_exit": 0}],
    }))

    def fake_exec(prompt, **kw):
        events = kw.get("event_sink")
        assert events is not None
        events.append({"type": "tool.completed", "name": "write_file",
                       "ok": False, "error_class": "schema_mismatch"})
        events.append({"type": "tool.completed", "name": "read_file",
                       "ok": True})
        events.append({"type": "item.completed",
                       "item": {"type": "agent_message", "text": "ok"}})
        events.append({"type": "turn.completed",
                       "usage": {"total_tokens": 10, "prompt_tokens": 5,
                                 "completion_tokens": 5}})
        return 0

    run = run_suite(suite, exec_fn=fake_exec)
    t = run["tasks"][0]
    assert t["tool_calls"] == 2 and t["malformed"] == 1
    assert t["parse_errors"] == 0 and t["malformed_rate"] == 0.5


def test_segmented_handoff_and_stop_on_failure(tmp_path):
    def factory(seg_id):
        class _P:
            protocol = "prompt"

            def __init__(self):
                self.n = 0

            def chat(self, messages, system=None, **kw):
                self.n += 1
                if seg_id == "s1":
                    if self.n == 1:
                        return _tool("write_file",
                                     {"path": "part.txt", "content": "half"})
                    return _Turn("done")
                return _Turn("stuck-does-nothing")

            def close(self):
                pass

        return _P()

    segs = [
        {"id": "s1", "prompt": "write part",
         "check": lambda wd: (wd / "part.txt").is_file()},
        {"id": "s2", "prompt": "write whole",
         "check": lambda wd: (wd / "whole.txt").is_file()},
    ]
    res = run_segmented(factory, segs, tmp_path, needles=[])
    assert res["cleared"] == "1/2", res
    assert [r["id"] for r in res["segments"]] == ["s1", "s2"]
    assert (tmp_path / "part.txt").is_file(), "s1's work survives s2's failure"
    assert res["tool_restriction"].startswith("none")


def test_segmented_malformed_attributed_per_segment(tmp_path):
    def factory(seg_id):
        class _P:
            protocol = "prompt"

            def chat(self, messages, system=None, **kw):
                if seg_id == "s1":
                    return _tool("write_file", {"content": "no-path"})
                return _Turn("done")

            def close(self):
                pass

        return _P()

    segs = [
        {"id": "s1", "prompt": "bad call",
         "check": lambda wd: True},
        {"id": "s2", "prompt": "fine",
         "check": lambda wd: True},
    ]
    res = run_segmented(factory, segs, tmp_path, needles=[])
    assert res["segments"][0]["malformed"] >= 1
    assert res["segments"][1]["malformed"] == 0
