"""DevPulse - Software Release Intelligence & Codebase Risk Analyzer.

Entry point CLI application providing actionable software engineering intelligence
from local Git repositories.
"""

import argparse
from pathlib import Path
import sys
from typing import Optional, Sequence

from config.settings import DEFAULT_CONFIG, DevPulseConfig
from models.exceptions import DevPulseError, InsufficientDataError
from services.anomaly_detector import AnomalyDetector
from services.commit_analyzer import CommitAnalyzer
from services.commit_classifier import CommitClassifier
from services.dsa_utils import (
    AnalysisHistoryStack,
    build_developer_map,
    build_file_stats_map,
    get_top_changed_files,
    get_top_risky_files,
)
from services.file_analyzer import FileAnalyzer
from services.git_analyzer import GitAnalyzer
from services.release_predictor import ReleasePredictor
from services.report_generator import ReportGenerator
from services.repository_analyzer import RepositoryAnalyzer
from services.risk_engine import RiskEngine
from services.storage import StorageService
from services.visualizer import Visualizer
from utils.dates import format_display_date
from utils.formatters import format_risk_badge, format_section_header


def run_analyze(args: argparse.Namespace) -> int:
    """Execute complete analysis pipeline and output intelligence dashboard."""
    repo_path = Path(args.repository).resolve()
    git_analyzer = GitAnalyzer(repo_path)
    branch = args.branch or git_analyzer.get_current_branch()
    total_files = git_analyzer.get_total_files()

    # Step 1: Extract commits
    commits = git_analyzer.extract_commits(
        max_count=args.commits,
        branch=args.branch,
    )

    if not commits:
        print(f"\n[!] Repository at '{repo_path}' has no commits to analyze on branch '{branch}'.")
        return 0

    # Step 2: DSA History Stack (demonstrating state management)
    history_stack: AnalysisHistoryStack[dict] = AnalysisHistoryStack()
    history_stack.push({"target": str(repo_path), "commit_count": len(commits)})

    # Step 3: Run Polymorphic Analyzers
    commit_analyzer = CommitAnalyzer()
    file_analyzer = FileAnalyzer()
    
    commit_data = commit_analyzer.analyze(commits)
    file_data = file_analyzer.analyze(commits)

    # Step 4: Classify Commits with TF-IDF + Naive Bayes
    classifier = CommitClassifier()
    classifications = classifier.classify_commits(commits)

    # Step 5: Statistical Anomaly Detection
    anomaly_detector = AnomalyDetector()
    anomalies = anomaly_detector.detect_all(commits)

    # Step 6: Risk Engine Evaluation
    risk_engine = RiskEngine()
    file_risks, release_risk = risk_engine.evaluate_repository(
        commits=commits,
        file_stats=file_data["file_stats_map"],
    )

    # Step 7: Polymorphic Repository Analyzer
    high_risk_count = sum(1 for r in file_risks.values() if r.level in ("HIGH", "CRITICAL"))
    repo_analyzer = RepositoryAnalyzer()
    repo_data = repo_analyzer.analyze({
        "repo_path": repo_path,
        "commits": commits,
        "total_files": total_files,
        "branch": branch,
        "anomalies_count": len(anomalies),
        "high_risk_files_count": high_risk_count,
    })
    repo_model = repo_data["repository"]

    # Step 8: Developer Activity Map
    dev_map = build_developer_map(commits)
    developers = list(dev_map.values())

    # Step 9: Release Prediction (Linear Regression)
    predictor = ReleasePredictor()
    prediction = None
    try:
        prediction = predictor.predict_next_period_churn(commits)
    except InsufficientDataError:
        prediction = None

    # Step 10: Top Risky Files using Priority Queue (heapq)
    top_risky = get_top_risky_files(file_risks, k=5)

    # =========================================================================
    # CLI Terminal Dashboard Output
    # =========================================================================
    print("=" * 64)
    print("DEVPULSE")
    print("SOFTWARE RELEASE INTELLIGENCE")
    print("=" * 29)
    print()
    print("Repository:")
    print(str(repo_path))
    print()
    print("Branch:")
    print(branch)
    print()
    print(f"Commits analyzed:\n{len(commits)}")
    print()
    print(f"Files analyzed:\n{len(file_data['file_stats_map'])}")
    print()
    print(f"Developers:\n{len(developers)}")
    print()
    print("---")
    print()
    print("## REPOSITORY HEALTH")
    print()
    print(f"Health Score: {repo_model.health_score:.0f}/100")
    print()
    print(f"Release Risk: {release_risk.level}")
    print()
    print("---")
    print()
    print("## TOP RISKY FILES")
    print()
    if top_risky:
        for idx, r in enumerate(top_risky, start=1):
            print(f"{idx}. {r.file_path:<36} {r.score:.0f}")
    else:
        print("No high-risk files identified.")
    print()
    print("---")
    print()
    print("## UNUSUAL COMMITS")
    print()
    if anomalies:
        print(f"{len(anomalies)} unusual commit(s) detected.")
        for a in anomalies[:3]:
            print(f"  * [{a.identifier}]: {a.reason}")
    else:
        print("No unusual commits detected.")
    print()
    print("---")
    print()
    print("## COMMIT CLASSIFICATION")
    print()
    for cat in DEFAULT_CONFIG.classifier.categories:
        count = classifications.get(cat, 0)
        if count > 0 or cat in ("Feature", "Bug Fix", "Refactor", "Other"):
            print(f"{cat:<15} {count}")
    print()
    print("---")
    print()
    print("## RELEASE FORECAST")
    print()
    if prediction:
        print("Predicted next-period change volume:")
        print(f"~ {int(round(prediction.predicted_volume)):,} lines")
    else:
        print("Insufficient historical intervals for regression forecast.")
    print()
    print("---")
    print()
    print("## RECOMMENDED REVIEW AREAS")
    print()
    if top_risky:
        for idx, r in enumerate(top_risky[:3], start=1):
            print(f"{idx}. {r.file_path}")
    else:
        print("Codebase stability indicators within normal parameters.")
    print()
    print("=" * 64)

    # Step 11: Export Reports & Persistence unless disabled
    out_dir = Path(args.output_dir or "reports")
    charts_dir = Path(args.charts_dir or "charts")

    if not args.no_reports:
        rep_gen = ReportGenerator(output_dir=out_dir)
        md_file = rep_gen.generate_markdown_report(
            repository=repo_model,
            commits=commits,
            churn_metrics=commit_data["churn_metrics"],
            developers=developers,
            top_files=file_data["top_modified_files"],
            file_risks=list(file_risks.values()),
            release_risk=release_risk,
            anomalies=anomalies,
            classifications=classifications,
            prediction=prediction,
        )
        csv_file = rep_gen.generate_summary_csv(
            repository=repo_model,
            commits=commits,
            churn_metrics=commit_data["churn_metrics"],
            release_risk=release_risk,
        )
        storage = StorageService(base_dir=out_dir)
        storage.save_analysis(
            output_dir=out_dir,
            commits=commits,
            file_stats=file_data["file_stats_map"],
            developers=developers,
            risks=list(file_risks.values()),
        )
        print(f"\n[+] Generated Markdown report : {md_file}")
        print(f"[+] Generated Summary CSV     : {csv_file}")
        print(f"[+] Persisted datasets to     : {out_dir}")

    # Step 12: Generate Matplotlib Charts
    if not args.no_charts:
        visualizer = Visualizer(output_dir=charts_dir)
        charts = visualizer.generate_all_charts(
            commits=commits,
            file_risks=list(file_risks.values()),
            top_files=file_data["top_modified_files"],
            developers=developers,
            prediction=prediction,
        )
        print(f"[+] Rendered {len(charts)} charts to      : {charts_dir}")

    return 0


def run_risky_files(args: argparse.Namespace) -> int:
    """Inspect top risky files with explanations and mitigations."""
    repo_path = Path(args.repository).resolve()
    git = GitAnalyzer(repo_path)
    commits = git.extract_commits()

    if not commits:
        print(f"No commits found in '{repo_path}'.")
        return 0

    risk_engine = RiskEngine()
    file_risks, _ = risk_engine.evaluate_repository(commits)
    top_k = get_top_risky_files(file_risks, k=args.top_k)

    print(format_section_header(f"Top {len(top_k)} Risky Codebase Files"))
    for idx, r in enumerate(top_k, start=1):
        if r.score < args.threshold:
            continue
        print(f"\n[{idx}] {r.file_path}")
        print(f"    Risk Score: {r.score:.1f} ({r.level})")
        print("    Primary Risk Factors:")
        for reason in r.reasons:
            print(f"      - {reason}")
        print(f"    Recommended Action: {r.recommended_action}")

    return 0


def run_commits(args: argparse.Namespace) -> int:
    """List and inspect recent commits with churn metrics."""
    repo_path = Path(args.repository).resolve()
    git = GitAnalyzer(repo_path)
    commits = git.extract_commits(
        max_count=args.limit,
        author=args.author,
        since=args.since,
        until=args.until,
    )

    print(format_section_header(f"Commit History ({len(commits)} commits)"))
    for c in reversed(commits):
        print(c)
    return 0


def run_developers(args: argparse.Namespace) -> int:
    """Analyze and display developer activity distribution."""
    repo_path = Path(args.repository).resolve()
    git = GitAnalyzer(repo_path)
    commits = git.extract_commits()

    dev_map = build_developer_map(commits)
    print(format_section_header("Developer Activity Distribution"))
    print(
        "Note: This information is for repository ownership analysis, not employee evaluation.\n"
    )
    for dev in sorted(dev_map.values(), key=lambda d: d.commit_count, reverse=True):
        print(f"  * {dev.summary()}")

    return 0


def run_predict(args: argparse.Namespace) -> int:
    """Run Linear Regression release change volume forecasting."""
    repo_path = Path(args.repository).resolve()
    git = GitAnalyzer(repo_path)
    commits = git.extract_commits()

    predictor = ReleasePredictor()
    try:
        pred = predictor.predict_next_period_churn(commits, period_freq=args.period)
        print(format_section_header("Release Change Volume Forecast"))
        print(pred.summary())
        print(f"Model Intercept: {pred.intercept:.1f}")
        print(f"Periods Analyzed: {pred.periods_count}")
        print(f"Methodology Note: {pred.confidence_note}")
    except InsufficientDataError as err:
        print(f"\n[!] Cannot predict release volume: {err}")
        return 1

    return 0


def run_classify(args: argparse.Namespace) -> int:
    """Run TF-IDF + Naive Bayes commit message classifier."""
    classifier = CommitClassifier()

    if args.message:
        category, confidence = classifier.predict(args.message)
        print(f"\nMessage: '{args.message}'")
        print(f"Classification: {category} (Confidence: {confidence:.2f})")
        return 0

    repo_path = Path(args.repository).resolve()
    git = GitAnalyzer(repo_path)
    commits = git.extract_commits(max_count=args.limit)

    classifications = classifier.classify_commits(commits)
    print(format_section_header(f"Commit Intent Classification ({len(commits)} commits)"))
    for cat, count in classifications.items():
        print(f"  {cat:<16}: {count}")

    return 0


def run_report(args: argparse.Namespace) -> int:
    """Generate Markdown and CSV reports for a repository."""
    # Reuse full analyze logic with no-charts
    args.no_charts = True
    args.no_reports = False
    args.commits = None
    args.branch = None
    args.charts_dir = None
    return run_analyze(args)


def run_charts(args: argparse.Namespace) -> int:
    """Generate all Matplotlib visualizations for a repository."""
    args.no_charts = False
    args.no_reports = True
    args.commits = None
    args.branch = None
    args.output_dir = None
    return run_analyze(args)


def build_parser() -> argparse.ArgumentParser:
    """Construct CLI argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="devpulse",
        description="DevPulse - Software Release Intelligence & Codebase Risk Analyzer",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Full repository intelligence analysis")
    p_analyze.add_argument("repository", help="Path to local Git repository")
    p_analyze.add_argument("--commits", "-n", type=int, default=None, help="Max commits to analyze")
    p_analyze.add_argument("--branch", "-b", type=str, default=None, help="Target branch")
    p_analyze.add_argument("--output-dir", type=str, default="reports", help="Reports directory")
    p_analyze.add_argument("--charts-dir", type=str, default="charts", help="Charts directory")
    p_analyze.add_argument("--no-charts", action="store_true", help="Skip chart generation")
    p_analyze.add_argument("--no-reports", action="store_true", help="Skip file report generation")
    p_analyze.set_defaults(func=run_analyze)

    # risky-files
    p_risky = subparsers.add_parser("risky-files", help="Identify high-risk codebase hotspot files")
    p_risky.add_argument("repository", help="Path to local Git repository")
    p_risky.add_argument("--top-k", "-k", type=int, default=5, help="Number of files to return")
    p_risky.add_argument("--threshold", "-t", type=float, default=0.0, help="Minimum risk score")
    p_risky.set_defaults(func=run_risky_files)

    # commits
    p_commits = subparsers.add_parser("commits", help="Inspect chronological commit stream")
    p_commits.add_argument("repository", help="Path to local Git repository")
    p_commits.add_argument("--limit", "-n", type=int, default=20, help="Limit number of commits")
    p_commits.add_argument("--author", "-a", type=str, default=None, help="Filter by author")
    p_commits.add_argument("--since", type=str, default=None, help="Since date (YYYY-MM-DD)")
    p_commits.add_argument("--until", type=str, default=None, help="Until date (YYYY-MM-DD)")
    p_commits.set_defaults(func=run_commits)

    # developers
    p_devs = subparsers.add_parser("developers", help="Inspect developer activity distribution")
    p_devs.add_argument("repository", help="Path to local Git repository")
    p_devs.set_defaults(func=run_developers)

    # predict
    p_predict = subparsers.add_parser("predict", help="Forecast next-release code change volume")
    p_predict.add_argument("repository", help="Path to local Git repository")
    p_predict.add_argument("--period", choices=["W", "ME"], default="W", help="Aggregation period")
    p_predict.set_defaults(func=run_predict)

    # classify
    p_classify = subparsers.add_parser("classify", help="Classify commit intent messages")
    p_classify.add_argument("repository", nargs="?", default=".", help="Path to repository")
    p_classify.add_argument("--message", "-m", type=str, default=None, help="Test a single message")
    p_classify.add_argument("--limit", "-n", type=int, default=50, help="Limit commit count")
    p_classify.set_defaults(func=run_classify)

    # report
    p_report = subparsers.add_parser("report", help="Generate Markdown and CSV reports")
    p_report.add_argument("repository", help="Path to local Git repository")
    p_report.add_argument("--output-dir", type=str, default="reports", help="Output directory")
    p_report.set_defaults(func=run_report)

    # charts
    p_charts = subparsers.add_parser("charts", help="Render all 7 Matplotlib charts")
    p_charts.add_argument("repository", help="Path to local Git repository")
    p_charts.add_argument("--charts-dir", type=str, default="charts", help="Output charts directory")
    p_charts.set_defaults(func=run_charts)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except DevPulseError as err:
        print(f"\n[DevPulse Error] {err}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130
    except Exception as err:
        print(f"\n[Unexpected Error] {err}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
