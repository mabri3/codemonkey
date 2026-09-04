"""Model-affinity batching (loop18, cycle 55).

Slot swaps cost seconds (page-cache reload + init), so never ping-pong a
single-slot server: group pending tasks by their routed model and run each
group contiguously. Group order = first appearance (stable for eval
baselines); order within a group is preserved.
"""

from __future__ import annotations
from collections import OrderedDict


def route_key(task: dict) -> str:
    """Which model slot a task will use (from resolver output if present)."""
    r = task.get("route")
    if isinstance(r, dict):
        return f"{r.get('provider', '')}/{r.get('model', '')}"
    return task.get("route_key", "")


def batch_by_model(tasks: list[dict]) -> list[list[dict]]:
    """Non-empty contiguous groups, model-affinity ordered,
    first-appearance group order, stable within groups."""
    groups: "OrderedDict[str, list]" = OrderedDict()
    for t in tasks:
        k = route_key(t)
        groups.setdefault(k, []).append(t)
    return [g for g in groups.values() if g]
