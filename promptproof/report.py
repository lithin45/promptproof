"""Human-readable reports + a JSON export the dashboard consumes."""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from .compare import ComparisonReport
from .store import list_runs, load_run
from .types import RunResult


def format_run_markdown(run: RunResult) -> str:
    rows = sorted(run.targets, key=lambda t: -t.mean_score)
    lines = [
        f"# {run.suite_name} — run `{run.run_id}`",
        "",
        f"_created {run.created_at}" + (f" · git {run.git_sha}" if run.git_sha else "") + "_",
        "",
        "| Target | Score | Pass rate | Cost (USD) | Mean latency |",
        "|---|---|---|---|---|",
    ]
    for t in rows:
        lines.append(
            f"| {t.target_id} | {t.mean_score:.3f} | {t.pass_rate:.0%} | "
            f"${t.total_cost_usd:.4f} | {t.mean_latency_ms:.0f} ms |"
        )
    return "\n".join(lines)


def format_comparison_markdown(cmp: ComparisonReport) -> str:
    verdict = "❌ REGRESSION DETECTED" if cmp.regressed else "✅ no regression"
    lines = [
        f"## {verdict} — {cmp.suite_name}",
        "",
        f"baseline `{cmp.baseline_run}` → candidate `{cmp.candidate_run}`",
        "",
        "| Target | Δ score | Δ pass | Status | Newly failing |",
        "|---|---|---|---|---|",
    ]
    for d in cmp.targets:
        nf = ", ".join(d.newly_failing) if d.newly_failing else "—"
        lines.append(
            f"| {d.target_id} | {d.score_delta:+.3f} | {d.pass_rate_delta:+.0%} | {d.status} | {nf} |"
        )
    return "\n".join(lines)


def export_for_dashboard(out_dir: str, root: str = ".") -> int:
    """Dump every stored run to <out_dir>/runs.json for the web dashboard."""
    os.makedirs(out_dir, exist_ok=True)
    runs = [asdict(load_run(r["run_id"], root)) for r in list_runs(root)]
    with open(os.path.join(out_dir, "runs.json"), "w", encoding="utf-8") as f:
        json.dump(runs, f, indent=2)
    return len(runs)
