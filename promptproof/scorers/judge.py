"""LLM-as-judge scorer.

Grades a generated field (e.g. the summary) against a reference using a model.
Offline, the MockProvider returns a deterministic overlap-based score so the
judge path is exercised in tests and the demo without any API key. Point
`provider`/`model` at a real API for genuine judging.
"""

from __future__ import annotations

from ..parsing import extract_json
from ..providers import get_provider
from .base import Scorer, register_scorer

JUDGE_TEMPLATE = """[[JUDGE]] You are grading a candidate summary against a reference summary.
Return ONLY JSON: {{"score": <float 0..1>, "reason": "<one sentence>"}}.
A score of 1.0 means the candidate captures the same key facts as the reference.
REFERENCE: {reference}
CANDIDATE: {candidate}
"""


@register_scorer("llm_judge")
class LlmJudge(Scorer):
    """config: { field, reference_key, provider, model, threshold }"""

    def score(self, case, output, parsed):
        field = self.config.get("field", "summary")
        ref_key = self.config.get("reference_key", field)
        candidate = parsed.get(field) if isinstance(parsed, dict) else None
        if candidate is None:
            candidate = output
        reference = case.expected.get(ref_key, "")

        prompt = JUDGE_TEMPLATE.format(reference=reference, candidate=candidate)
        provider = get_provider(self.config.get("provider", "mock"))
        resp = provider.complete(self.config.get("model", "mock-large"), prompt, {})
        verdict = extract_json(resp.text) or {}

        try:
            score = float(verdict.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        threshold = self.config.get("threshold", 0.6)
        return self._result(score, score >= threshold, verdict.get("reason", ""))
