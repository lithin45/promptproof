"""The runner: execute every target over every case, score, aggregate."""

from __future__ import annotations

import subprocess
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .config import load_dataset, read_prompt
from .parsing import extract_json
from .providers import get_provider
from .scorers import get_scorer
from .types import CaseResult, RunResult, Suite, Target, TargetResult
from .util import slug


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return None


def _render(template: str, case) -> str:
    return template.replace("{{input}}", case.input).replace("{{id}}", case.id)


def _weighted(scores) -> float:
    total_w = sum(s.weight for s in scores) or 1.0
    return sum(s.score * s.weight for s in scores) / total_w


def _run_case(target: Target, provider, template: str, scorers, case) -> CaseResult:
    prompt = _render(template, case)
    try:
        resp = provider.complete(target.model, prompt, target.params)
    except Exception as e:  # provider/network failure shouldn't crash the whole run
        return CaseResult(case_id=case.id, input=case.input, output="", error=str(e))

    parsed = extract_json(resp.text)
    score_results = [sc.score(case, resp.text, parsed) for sc in scorers]
    weighted = _weighted(score_results)
    passed = all(s.passed for s in score_results) if score_results else False
    return CaseResult(
        case_id=case.id,
        input=case.input,
        output=resp.text,
        parsed=parsed,
        scores=score_results,
        weighted_score=round(weighted, 4),
        passed=passed,
        tokens_in=resp.tokens_in,
        tokens_out=resp.tokens_out,
        cost_usd=round(resp.cost_usd, 6),
        latency_ms=resp.latency_ms,
    )


def _aggregate(target: Target, cases: list[CaseResult]) -> TargetResult:
    n = len(cases) or 1
    return TargetResult(
        target_id=target.id,
        provider=target.provider,
        model=target.model,
        cases=cases,
        mean_score=round(sum(c.weighted_score for c in cases) / n, 4),
        pass_rate=round(sum(1 for c in cases if c.passed) / n, 4),
        total_cost_usd=round(sum(c.cost_usd for c in cases), 6),
        mean_latency_ms=round(sum(c.latency_ms for c in cases) / n, 1),
        total_tokens=sum(c.tokens_in + c.tokens_out for c in cases),
    )


def run_suite(suite: Suite, cases=None, concurrency: int = 4, notes: str = "", limit=None) -> RunResult:
    cases = cases if cases is not None else load_dataset(suite)
    if limit:
        cases = cases[:limit]
    scorers = [get_scorer(s) for s in suite.scorers]

    target_results: list[TargetResult] = []
    for target in suite.targets:
        template = read_prompt(suite, target.prompt_path)
        provider = get_provider(target.provider)
        if concurrency > 1 and len(cases) > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as ex:
                results = list(
                    ex.map(lambda c: _run_case(target, provider, template, scorers, c), cases)
                )
        else:
            results = [_run_case(target, provider, template, scorers, c) for c in cases]
        target_results.append(_aggregate(target, results))

    now = datetime.now()
    run_id = f"{slug(suite.name)}-{now.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    return RunResult(
        run_id=run_id,
        suite_name=suite.name,
        created_at=now.isoformat(timespec="milliseconds"),
        targets=target_results,
        git_sha=_git_sha(),
        notes=notes,
    )
