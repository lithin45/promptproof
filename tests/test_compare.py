"""Regression-detection tests against the example suites."""

import os

from promptproof.compare import compare_runs
from promptproof.config import load_suite
from promptproof.runner import run_suite

DIR = os.path.join(os.path.dirname(__file__), "..", "examples", "support_ticket_triage")


def _run(name):
    return run_suite(load_suite(os.path.join(DIR, name)), concurrency=2)


def test_no_regression_against_self():
    run = _run("suite.yaml")
    cmp = compare_runs(run, run, {"max_score_drop": 0.02, "max_pass_rate_drop": 0.05})
    assert not cmp.regressed
    assert all(not d.regressed for d in cmp.targets)


def test_regression_detected_on_broken_prompt():
    baseline = _run("suite.yaml")
    candidate = _run("suite_regressed.yaml")
    cmp = compare_runs(baseline, candidate, {"max_score_drop": 0.02, "max_pass_rate_drop": 0.05})

    assert cmp.regressed

    broken = next(d for d in cmp.targets if d.target_id == "large + fewshot")
    assert broken.regressed
    assert broken.score_delta < 0
    assert broken.newly_failing  # cases that started failing

    untouched = next(d for d in cmp.targets if d.target_id == "small + basic")
    assert not untouched.regressed
