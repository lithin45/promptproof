"""promptproof CLI.

  promptproof run <suite.yaml> [--set-baseline] [--fail-on-regression]
  promptproof compare [--baseline ID] [--candidate ID] [--suite NAME]
  promptproof report [RUN_ID]
  promptproof list
  promptproof baseline <RUN_ID>
  promptproof export [--out DIR]

Exit codes: 0 = ok, 1 = regression detected (for CI gating), 2 = usage error.
"""

from __future__ import annotations

import argparse
import sys

from .compare import compare_runs
from .config import load_suite
from .report import (
    export_for_dashboard,
    format_comparison_markdown,
    format_run_markdown,
)
from .runner import run_suite
from .store import (
    latest_run,
    list_runs,
    load_baseline,
    load_run,
    save_run,
    set_baseline,
)


def _cmd_run(args) -> int:
    suite = load_suite(args.suite)
    print(
        f"▶ Running suite '{suite.name}' — {len(suite.targets)} target(s)…",
        file=sys.stderr,
    )
    run = run_suite(suite, concurrency=args.concurrency, notes=args.notes or "")
    path = save_run(run, args.root)
    print(format_run_markdown(run))
    print(f"\n💾 saved → {path}", file=sys.stderr)

    if args.set_baseline:
        bp = set_baseline(run.run_id, args.root)
        print(f"📌 baseline set → {bp}", file=sys.stderr)
        return 0

    base = load_baseline(suite.name, args.root)
    if base:
        cmp = compare_runs(base, run, suite.thresholds)
        print("\n" + format_comparison_markdown(cmp))
        if cmp.regressed and args.fail_on_regression:
            return 1
    return 0


def _resolve(args):
    candidate = (
        load_run(args.candidate, args.root) if args.candidate
        else latest_run(args.root, args.suite_name)
    )
    if candidate is None:
        print("No candidate run found. Run the suite first.", file=sys.stderr)
        return None, None
    baseline = (
        load_run(args.baseline, args.root) if args.baseline
        else load_baseline(candidate.suite_name, args.root)
    )
    if baseline is None:
        print("No baseline set. Use: promptproof baseline <RUN_ID>", file=sys.stderr)
        return None, None
    return baseline, candidate


def _cmd_compare(args) -> int:
    baseline, candidate = _resolve(args)
    if not candidate or not baseline:
        return 2
    thresholds = {}
    if args.max_score_drop is not None:
        thresholds["max_score_drop"] = args.max_score_drop
    if args.max_pass_drop is not None:
        thresholds["max_pass_rate_drop"] = args.max_pass_drop
    cmp = compare_runs(baseline, candidate, thresholds)
    print(format_comparison_markdown(cmp))
    return 1 if cmp.regressed else 0


def _cmd_report(args) -> int:
    run = load_run(args.run_id, args.root) if args.run_id else latest_run(args.root)
    if run is None:
        print("No runs found.", file=sys.stderr)
        return 2
    print(format_run_markdown(run))
    return 0


def _cmd_list(args) -> int:
    runs = list_runs(args.root)
    if not runs:
        print("No runs yet.", file=sys.stderr)
        return 0
    for r in runs:
        best = max((t["mean_score"] for t in r["targets"]), default=0.0)
        print(f"{r['run_id']:<40} {r['suite_name']:<28} best={best:.3f}  {r['created_at']}")
    return 0


def _cmd_baseline(args) -> int:
    path = set_baseline(args.run_id, args.root)
    print(f"📌 baseline set → {path}")
    return 0


def _cmd_export(args) -> int:
    n = export_for_dashboard(args.out, args.root)
    print(f"📤 exported {n} run(s) → {args.out}/runs.json")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="promptproof", description="LLM eval & regression harness.")
    p.add_argument("--root", default=".", help="Project root holding .promptproof/ (default: .)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run an eval suite.")
    r.add_argument("suite", help="Path to suite YAML/JSON.")
    r.add_argument("--concurrency", type=int, default=8)
    r.add_argument("--set-baseline", action="store_true", help="Save this run as the baseline.")
    r.add_argument("--fail-on-regression", action="store_true", help="Exit 1 if it regresses vs baseline.")
    r.add_argument("--notes", default="")
    r.set_defaults(func=_cmd_run)

    c = sub.add_parser("compare", help="Compare a run to the baseline (exit 1 on regression).")
    c.add_argument("--baseline", help="Baseline run id (default: stored baseline).")
    c.add_argument("--candidate", help="Candidate run id (default: latest run).")
    c.add_argument("--suite-name", help="Restrict 'latest' to this suite.")
    c.add_argument("--max-score-drop", type=float, default=None)
    c.add_argument("--max-pass-drop", type=float, default=None)
    c.set_defaults(func=_cmd_compare)

    rp = sub.add_parser("report", help="Print a leaderboard for a run.")
    rp.add_argument("run_id", nargs="?", help="Run id (default: latest).")
    rp.set_defaults(func=_cmd_report)

    sub.add_parser("list", help="List stored runs.").set_defaults(func=_cmd_list)

    b = sub.add_parser("baseline", help="Set a run as the baseline.")
    b.add_argument("run_id")
    b.set_defaults(func=_cmd_baseline)

    e = sub.add_parser("export", help="Export runs as JSON for the dashboard.")
    e.add_argument("--out", default="dashboard/public/data")
    e.set_defaults(func=_cmd_export)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
