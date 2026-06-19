"""Integration test: run the example suite and check the leaderboard story."""

import os

from promptproof.config import load_suite
from promptproof.runner import run_suite

SUITE = os.path.join(
    os.path.dirname(__file__), "..", "examples", "support_ticket_triage", "suite.yaml"
)


def test_example_run_leaderboard():
    suite = load_suite(SUITE)
    run = run_suite(suite, concurrency=2)
    by = {t.target_id: t for t in run.targets}

    assert set(by) == {"small + basic", "small + fewshot", "large + basic", "large + fewshot"}

    # Few-shot examples fix the hard cases, so few-shot > basic at each model tier.
    assert by["small + fewshot"].mean_score > by["small + basic"].mean_score
    assert by["large + fewshot"].mean_score > by["large + basic"].mean_score

    # Headline insight: prompt quality beats raw model size here.
    assert by["small + fewshot"].mean_score > by["large + basic"].mean_score

    # The best overall is the big model with the good prompt...
    best = max(by.values(), key=lambda t: t.mean_score)
    assert best.target_id == "large + fewshot"

    # ...but it costs more than the small model with the same prompt.
    assert by["large + fewshot"].total_cost_usd > by["small + fewshot"].total_cost_usd

    # Few-shot lifts the pass rate (the 4 hard cases now classify correctly).
    assert by["small + fewshot"].pass_rate > by["small + basic"].pass_rate
