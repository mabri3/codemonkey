"""codemonkey eval (loop5, cycle 24): golden-task evaluation harness.

Runs YAML golden suites against the REAL exec path and scores:
  - stdout contract (expected contains / not-contains)
  - exit code
  - required tool trajectory (tool names in call order, subset match)
Results land in build/eval/results.json (pass rate, per-task detail, tokens,
wall time).

Suite shape:
  name: my-suite
  tasks:
    - id: pong
      prompt: "Reply with exactly: pong"
      expect_stdout_contains: ["pong"]
      expect_exit: 0
      expect_tools: []            # subset of tool names, in order
      sandbox: workspace-write    # optional exec kwargs
      approval: never
      provider: local             # optional; default from config
      ephemeral: true
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

import yaml


def load_suite(path: Path) -> dict:
    """Load + validate a YAML suite. Raises ValueError on malformed input."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"cannot read suite {path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError(f"suite {path} must be a mapping with a 'tasks' list")
    for i, task in enumerate(data["tasks"]):
        if not isinstance(task, dict) or not task.get("id") or not task.get("prompt"):
            raise ValueError(f"suite task #{i} needs 'id' and 'prompt'")
    return data


def _trajectory_from_events(events: list) -> list[str]:
    """Tool names in first-call order from a --json event list."""
    seen: list[str] = []
    for ev in events:
        if ev.get("type") == "tool.started":
            name = ev.get("name")
            if name and name not in seen:
                seen.append(name)
    return seen


def _score_task(task: dict, *, exit_code: int, stdout: str,
                events: list, wall: float) -> dict:
    checks = {"stdout": True, "exit": True, "trajectory": True}
    detail = {}

    for needle in task.get("expect_stdout_contains") or []:
        if needle not in stdout:
            checks["stdout"] = False
            detail.setdefault("missing_stdout", []).append(needle)
    for needle in task.get("expect_stdout_not_contains") or []:
        if needle in stdout:
            checks["stdout"] = False
            detail.setdefault("forbidden_stdout_found", []).append(needle)

    want_exit = task.get("expect_exit", 0)
    if exit_code != want_exit:
        checks["exit"] = False
        detail["exit_code"] = {"want": want_exit, "got": exit_code}

    want_tools = task.get("expect_tools") or []
    if want_tools:
        got = _trajectory_from_events(events)
        # subset in order
        it = iter(got)
        if not all(t in it for t in want_tools):
            checks["trajectory"] = False
            detail["trajectory"] = {"want": want_tools, "got": got}

    ok = all(checks.values())

    # loop38 cycle 78: rubric steps compose into task scoring. The rubric
    # grades the same stdout text; a failing rubric fails the task even when
    # every other check passes (rubric-only tasks — no stdout contract — are
    # allowed: an empty checks dict is all-true, the rubric still decides).
    rubric_result = None
    if task.get("rubric"):
        from .rubrics import rubric_from_yaml_steps, score_rubric

        rubric_result = score_rubric(
            stdout, rubric_from_yaml_steps(task.get("rubric") or []))
        if not rubric_result["passed"]:
            ok = False

    result = {
        "id": task["id"],
        "ok": ok,
        "checks": checks,
        "detail": detail,
        "tokens": _tokens_from_events(events),
        "wall_seconds": round(wall, 2),
    }
    if rubric_result is not None:
        result["rubric"] = rubric_result
    return result


def _tokens_from_events(events: list) -> int:
    total = 0
    for ev in events:
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage") or {}
            total += int(usage.get("total_tokens") or 0)
    return total


def _window_depth_from_events(events: list) -> int:
    """Max prompt_tokens across turns — the deepest context the model saw."""
    depth = 0
    for ev in events:
        if ev.get("type") == "turn.completed":
            usage = ev.get("usage") or {}
            depth = max(depth, int(usage.get("prompt_tokens") or 0))
    return depth


def run_suite(suite_path: Path, *, exec_fn=None,
              out_dir: Optional[Path] = None,
              early_stop: bool = False, delta: float = 0.05) -> dict:
    """Run every task through the real exec path and score it.

    `exec_fn` defaults to codemonkey.exec.run_exec; tests may inject a fake
    with the same signature. With `early_stop`, the fixed-n Hoeffding gate
    (certify.hoeffding_gate, kind "hoeffding-gate") is replayed over the
    observed outcomes after each task; when it settles, the remaining tasks
    are skipped and `results["certificate"]` carries the gate verdict.
    Returns the results dict and (if out_dir given) writes results.json
    there.
    """
    if exec_fn is None:
        from .exec import run_exec as exec_fn

    suite = load_suite(suite_path)
    results = {"suite": suite.get("name", Path(suite_path).stem),
               "tasks": [], "started": time.time()}

    # loop18 cycle 55: model-affinity ordering — resolve a route key per task,
    # run same-model tasks contiguously (single-slot servers: fewer swaps),
    # but report results in suite order for stable baselines.
    from .affinity import route_key as _rk, batch_by_model as _bbm

    for pos, task in enumerate(suite["tasks"]):
        task["_suite_pos"] = pos
        task["_route_key"] = _rk({"route": {"provider": task.get("provider") or "",
                                            "model": task.get("model") or ""}})
    ordered = [t for group in _bbm(suite["tasks"]) for t in group]
    results_by_pos = {}
    outcomes: list[bool] = []
    certificate: Optional[dict] = None
    for task in ordered:
        events: list = []
        started = time.time()

        def collect(ev, _events=events):
            events.append(ev)

        code = exec_fn(
            task["prompt"],
            json_mode=True,
            event_sink=events,
            sandbox=task.get("sandbox"),
            approval=task.get("approval"),
            provider_name=task.get("provider"),
            ephemeral=task.get("ephemeral", True),
        )
        wall = time.time() - started
        # stdout in json mode = the event stream; the graded answer text lives
        # in item.completed agent_message entries.
        stdout_text = "\n".join(
            str(ev.get("item", {}).get("text") or "")
            for ev in events
            if ev.get("type") == "item.completed"
            and ev.get("item", {}).get("type") == "agent_message"
        )
        scored = _score_task(task, exit_code=code, stdout=stdout_text,
                             events=events, wall=wall)
        scored["stdout"] = stdout_text[:2000]
        scored["window_depth"] = _window_depth_from_events(events)
        # loop7 cycle 33: journal-derived failure-class stats for the run
        try:
            from .journal import class_summary as _cs, read_thread as _rt

            # 31F1: the thread id comes from the run itself (thread.started);
            # `_journal_thread` stays as an explicit per-task override.
            jt = task.get("_journal_thread") or next(
                (ev.get("thread_id") for ev in events
                 if ev.get("type") == "thread.started" and ev.get("thread_id")),
                "",
            )
            if jt:
                scored["journal_thread"] = jt
                scored["journal_classes"] = _cs(_rt(jt))
        except OSError:
            pass
        scored["route_key"] = task.get("_route_key", "")
        results_by_pos[task["_suite_pos"]] = scored
        if early_stop:
            outcomes.append(bool(scored["ok"]))
            if len(outcomes) >= 2:
                from .certify import hoeffding_gate as _gate

                gate = _gate(outcomes, delta=delta)
                if gate["certified_pass"] is not None:
                    gate["stopped_at_task"] = task["id"]
                    certificate = gate
                    break

    # restore suite order for stable baselines
    results["tasks"] = [results_by_pos[p] for p in sorted(results_by_pos)]
    if certificate is not None:
        certificate["total"] = len(outcomes)
        certificate["stopped_early"] = len(outcomes) < len(ordered)
        results["certificate"] = certificate
        results["stopped_early"] = True
    else:
        results["stopped_early"] = False

    results["pass_rate"] = round(
        sum(1 for t in results["tasks"] if t["ok"]) / max(1, len(results["tasks"])), 3
    )
    results["total_tokens"] = sum(t["tokens"] for t in results["tasks"])
    results["wall_seconds"] = round(sum(t["wall_seconds"] for t in results["tasks"]), 2)
    results["finished"] = time.time()

    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    return results


def write_baseline(results: dict, path: Path) -> None:
    """Versioned baseline: per-task ok + pass_rate + token/wall totals."""
    baseline = {
        "suite": results["suite"],
        "pass_rate": results["pass_rate"],
        "total_tokens": results["total_tokens"],
        "wall_seconds": results["wall_seconds"],
        "tasks": {t["id"]: {"ok": t["ok"]} for t in results["tasks"]},
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(baseline, indent=2))


def check_regression(results: dict, baseline_path: Path) -> tuple[bool, list[str]]:
    """Compare a run against the baseline. Returns (ok, regressions).

    A regression is: a task that passed before and fails now, or pass_rate
    dropping. Improvements are noted but never fail the check.
    """
    if not baseline_path.is_file():
        return True, []  # no baseline yet -> nothing to regress against
    base = json.loads(baseline_path.read_text())
    regressions = []
    for t in results["tasks"]:
        was = (base.get("tasks") or {}).get(t["id"], {}).get("ok")
        if was is True and not t["ok"]:
            regressions.append(f"{t['id']}: passed in baseline, fails now")
    if results["pass_rate"] < float(base.get("pass_rate", 0)):
        regressions.append(
            f"pass_rate dropped: {base.get('pass_rate')} -> {results['pass_rate']}"
        )
    return (not regressions), regressions
