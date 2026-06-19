"""Persist runs as plain JSON under .promptproof/ (diffable, dashboard-friendly)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from .types import RunResult
from .util import slug


def _runs_dir(root: str) -> str:
    return os.path.join(root, ".promptproof", "runs")


def _baselines_dir(root: str) -> str:
    return os.path.join(root, ".promptproof", "baselines")


def save_run(run: RunResult, root: str = ".") -> str:
    d = _runs_dir(root)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, run.run_id + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(run), f, indent=2)
    return path


def load_run(run_id: str, root: str = ".") -> RunResult:
    with open(os.path.join(_runs_dir(root), run_id + ".json"), encoding="utf-8") as f:
        return RunResult.from_dict(json.load(f))


def list_runs(root: str = ".") -> list[dict]:
    d = _runs_dir(root)
    if not os.path.isdir(d):
        return []
    runs = []
    for fn in os.listdir(d):
        if fn.endswith(".json"):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                runs.append(json.load(f))
    runs.sort(key=lambda r: r["created_at"])
    return runs


def latest_run(root: str = ".", suite_name: str | None = None) -> RunResult | None:
    runs = list_runs(root)
    if suite_name:
        runs = [r for r in runs if r["suite_name"] == suite_name]
    if not runs:
        return None
    return load_run(runs[-1]["run_id"], root)


def set_baseline(run_id: str, root: str = ".") -> str:
    run = load_run(run_id, root)
    d = _baselines_dir(root)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, slug(run.suite_name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(run), f, indent=2)
    return path


def load_baseline(suite_name: str, root: str = ".") -> RunResult | None:
    path = os.path.join(_baselines_dir(root), slug(suite_name) + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return RunResult.from_dict(json.load(f))
