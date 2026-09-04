"""Cycle 55 (loop18): model-affinity batching."""

from __future__ import annotations

from codemonkey.affinity import batch_by_model, route_key


def _t(tid, model, provider="local"):
    return {"id": tid, "route": {"provider": provider, "model": model}}


def test_grouping_by_routed_model():
    tasks = [_t("a", "m1"), _t("b", "m2"), _t("c", "m1"), _t("d", "m3")]
    groups = batch_by_model(tasks)
    assert [[t["id"] for t in g] for g in groups] == [
        ["a", "c"], ["b"], ["d"]]


def test_first_appearance_group_order():
    tasks = [_t("a", "m2"), _t("b", "m1"), _t("c", "m2")]
    groups = batch_by_model(tasks)
    # m2 group first (first appearance), then m1
    assert [[t["id"] for t in g] for g in groups] == [["a", "c"], ["b"]]


def test_order_preserved_within_group():
    tasks = [_t("x", "m1"), _t("y", "m1"), _t("z", "m1")]
    groups = batch_by_model(tasks)
    assert [t["id"] for t in groups[0]] == ["x", "y", "z"]


def test_empty_and_single():
    assert batch_by_model([]) == []
    one = [_t("only", "m1")]
    assert batch_by_model(one) == [one]


def test_mixed_route_shapes():
    tasks = [
        _t("a", "m1"),
        {"id": "b", "route_key": "local/m2"},  # pre-resolved key form
        _t("c", "m1"),
    ]
    groups = batch_by_model(tasks)
    assert [[t["id"] for t in g] for g in groups] == [["a", "c"], ["b"]]
    assert route_key(_t("a", "m1")) == "local/m1"
