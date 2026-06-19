"""Core domain model for PromptProof.

Everything is a plain dataclass so runs serialize cleanly to JSON (via
``dataclasses.asdict``) and reload with the explicit ``from_dict`` helpers
below. We avoid a heavy validation dependency on purpose: the engine has zero
third-party requirements beyond PyYAML for reading suite files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Suite definition (loaded from YAML/JSON)
# --------------------------------------------------------------------------- #
@dataclass
class Case:
    """A single test case: an input and the gold/reference fields to score against."""

    id: str
    input: str
    expected: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScorerSpec:
    """References a registered scorer by name, with a weight and free-form config."""

    name: str
    weight: float = 1.0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Target:
    """One thing under test: a provider + model + prompt template + params."""

    id: str
    provider: str
    model: str
    prompt_path: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class Suite:
    name: str
    description: str
    dataset_path: str
    targets: list[Target]
    scorers: list[ScorerSpec]
    thresholds: dict[str, float] = field(default_factory=dict)
    base_dir: str = "."


# --------------------------------------------------------------------------- #
# Results (produced by the runner, persisted by the store)
# --------------------------------------------------------------------------- #
@dataclass
class ScoreResult:
    scorer: str
    score: float  # normalized 0..1
    weight: float
    passed: bool
    detail: str = ""


@dataclass
class CaseResult:
    case_id: str
    input: str
    output: str
    parsed: Any = None
    scores: list[ScoreResult] = field(default_factory=list)
    weighted_score: float = 0.0
    passed: bool = False
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str | None = None


@dataclass
class TargetResult:
    target_id: str
    provider: str
    model: str
    cases: list[CaseResult] = field(default_factory=list)
    mean_score: float = 0.0
    pass_rate: float = 0.0
    total_cost_usd: float = 0.0
    mean_latency_ms: float = 0.0
    total_tokens: int = 0


@dataclass
class RunResult:
    run_id: str
    suite_name: str
    created_at: str
    targets: list[TargetResult] = field(default_factory=list)
    git_sha: str | None = None
    notes: str = ""

    # ---- (de)serialization ------------------------------------------------ #
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RunResult":
        targets = []
        for t in d.get("targets", []):
            cases = []
            for c in t.get("cases", []):
                scores = [ScoreResult(**s) for s in c.get("scores", [])]
                c = {**c, "scores": scores}
                cases.append(CaseResult(**c))
            t = {**t, "cases": cases}
            targets.append(TargetResult(**t))
        return RunResult(
            run_id=d["run_id"],
            suite_name=d["suite_name"],
            created_at=d["created_at"],
            targets=targets,
            git_sha=d.get("git_sha"),
            notes=d.get("notes", ""),
        )
