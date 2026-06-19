"""Load suites (YAML or JSON), datasets (JSONL), and prompt templates."""

from __future__ import annotations

import json
import os

from .types import Case, ScorerSpec, Suite, Target


def _load_structured(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if path.endswith((".yaml", ".yml")):
        import yaml  # lazy: only needed for YAML suites

        return yaml.safe_load(text)
    return json.loads(text)


def load_suite(path: str) -> Suite:
    data = _load_structured(path)
    base_dir = os.path.dirname(os.path.abspath(path))
    targets = [
        Target(
            id=t["id"],
            provider=t["provider"],
            model=t["model"],
            prompt_path=t["prompt"],
            params=t.get("params", {}),
        )
        for t in data["targets"]
    ]
    scorers = [
        ScorerSpec(name=s["name"], weight=float(s.get("weight", 1.0)), config=s.get("config", {}))
        for s in data["scorers"]
    ]
    return Suite(
        name=data["name"],
        description=data.get("description", ""),
        dataset_path=data["dataset"],
        targets=targets,
        scorers=scorers,
        thresholds={k: float(v) for k, v in data.get("thresholds", {}).items()},
        base_dir=base_dir,
    )


def load_dataset(suite: Suite) -> list[Case]:
    path = os.path.join(suite.base_dir, suite.dataset_path)
    cases: list[Case] = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno}: invalid JSONL — {e}") from e
            cases.append(
                Case(
                    id=str(d["id"]),
                    input=d["input"],
                    expected=d.get("expected", {}),
                    metadata=d.get("metadata", {}),
                )
            )
    if not cases:
        raise ValueError(f"Dataset {path} contained no cases.")
    return cases


def read_prompt(suite: Suite, prompt_path: str) -> str:
    with open(os.path.join(suite.base_dir, prompt_path), encoding="utf-8") as f:
        return f.read()
