"""Scorer abstraction + registry.

A Scorer grades one case's output and returns a normalized 0..1 score plus a
pass/fail flag and a human-readable detail string. Scorers are referenced by
name from the suite file and combined with weights by the runner.
"""

from __future__ import annotations

from ..types import Case, ScoreResult

_SCORERS: dict[str, type["Scorer"]] = {}


def register_scorer(name: str):
    def deco(cls: type["Scorer"]) -> type["Scorer"]:
        cls._name = name
        _SCORERS[name] = cls
        return cls

    return deco


def get_scorer(spec) -> "Scorer":
    if spec.name not in _SCORERS:
        raise ValueError(f"Unknown scorer {spec.name!r}. Registered: {sorted(_SCORERS)}")
    return _SCORERS[spec.name](spec.config, spec.weight)


class Scorer:
    _name = "scorer"

    def __init__(self, config: dict, weight: float):
        self.config = config
        self.weight = weight

    @property
    def name(self) -> str:
        return self._name

    def score(self, case: Case, output: str, parsed) -> ScoreResult:
        raise NotImplementedError

    def _result(self, score: float, passed: bool, detail: str = "") -> ScoreResult:
        return ScoreResult(
            scorer=self.name,
            score=float(max(0.0, min(1.0, score))),
            weight=self.weight,
            passed=bool(passed),
            detail=detail,
        )
