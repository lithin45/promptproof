"""Regression detection: diff a candidate run against a baseline.

A target "regressed" if its mean score dropped by more than `max_score_drop`
or its pass rate dropped by more than `max_pass_rate_drop`. The overall run
regressed if any target did — that's what the CI gate keys off of.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .types import RunResult, TargetResult

DEFAULT_SCORE_DROP = 0.02
DEFAULT_PASS_DROP = 0.05


@dataclass
class TargetDelta:
    target_id: str
    baseline_score: float
    candidate_score: float
    score_delta: float
    baseline_pass_rate: float
    candidate_pass_rate: float
    pass_rate_delta: float
    cost_delta: float
    latency_delta: float
    regressed: bool
    status: str  # ok | regressed | improved | new | removed
    newly_failing: list[str] = field(default_factory=list)


@dataclass
class ComparisonReport:
    suite_name: str
    baseline_run: str
    candidate_run: str
    regressed: bool
    targets: list[TargetDelta] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _by_id(run: RunResult) -> dict[str, TargetResult]:
    return {t.target_id: t for t in run.targets}


def _failing(t: TargetResult) -> set[str]:
    return {c.case_id for c in t.cases if not c.passed}


def compare_runs(
    baseline: RunResult, candidate: RunResult, thresholds: dict | None = None
) -> ComparisonReport:
    thresholds = thresholds or {}
    score_drop = thresholds.get("max_score_drop", DEFAULT_SCORE_DROP)
    pass_drop = thresholds.get("max_pass_rate_drop", DEFAULT_PASS_DROP)

    b, c = _by_id(baseline), _by_id(candidate)
    deltas: list[TargetDelta] = []
    any_regressed = False

    for tid in sorted(set(b) | set(c)):
        bt, ct = b.get(tid), c.get(tid)

        if bt and not ct:
            deltas.append(TargetDelta(tid, bt.mean_score, 0.0, -bt.mean_score, bt.pass_rate,
                                      0.0, -bt.pass_rate, 0.0, 0.0, False, "removed"))
            continue
        if ct and not bt:
            deltas.append(TargetDelta(tid, 0.0, ct.mean_score, ct.mean_score, 0.0, ct.pass_rate,
                                      ct.pass_rate, ct.total_cost_usd, ct.mean_latency_ms, False, "new"))
            continue

        score_delta = round(ct.mean_score - bt.mean_score, 4)
        pass_delta = round(ct.pass_rate - bt.pass_rate, 4)
        regressed = (score_delta < -score_drop) or (pass_delta < -pass_drop)
        improved = score_delta > score_drop
        any_regressed = any_regressed or regressed

        deltas.append(
            TargetDelta(
                target_id=tid,
                baseline_score=bt.mean_score,
                candidate_score=ct.mean_score,
                score_delta=score_delta,
                baseline_pass_rate=bt.pass_rate,
                candidate_pass_rate=ct.pass_rate,
                pass_rate_delta=pass_delta,
                cost_delta=round(ct.total_cost_usd - bt.total_cost_usd, 6),
                latency_delta=round(ct.mean_latency_ms - bt.mean_latency_ms, 1),
                regressed=regressed,
                status="regressed" if regressed else "improved" if improved else "ok",
                newly_failing=sorted(_failing(ct) - _failing(bt)),
            )
        )

    return ComparisonReport(
        suite_name=candidate.suite_name,
        baseline_run=baseline.run_id,
        candidate_run=candidate.run_id,
        regressed=any_regressed,
        targets=deltas,
    )
