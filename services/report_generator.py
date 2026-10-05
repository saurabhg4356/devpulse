"""Report generation service for DevPulse.

Generates human-readable Markdown analysis reports (repository_report.md)
and machine-readable executive summary CSV files (repository_summary.csv).
All recommendations are presented as engineering suggestions, not automated dogma.
"""

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from models.commit import Commit
from models.developer import Developer
from models.exceptions import ReportGenerationError
from models.repository import Repository
from models.risk import ReleaseRisk, RiskResult
from services.anomaly_detector import Anomaly
from services.dsa_utils import get_top_risky_files
from services.release_predictor import PredictionResult
from utils.dates import format_display_date, format_iso_datetime
from utils.formatters import format_lines_diff, format_number


class ReportGenerator:
    """Renders comprehensive Markdown and CSV analysis reports."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        repository: Repository,
        commits: Sequence[Commit],
        churn_metrics: Dict[str, Any],
        developers: Sequence[Developer],
        top_files: Sequence[Dict[str, Any]],
        file_risks: Sequence[RiskResult],
        release_risk: ReleaseRisk,
        anomalies: Sequence[Anomaly],
        classifications: Dict[str, int],
        prediction: Optional[PredictionResult] = None,
        custom_filename: str = "repository_report.md",
    ) -> Path:
        """Render full repository Markdown report with all required sections."""
        out_path = self.output_dir / custom_filename
        now = datetime.now(timezone.utc)
        top_risky = get_top_risky_files(file_risks, k=10)

        lines: List[str] = [
            "# DevPulse Repository Report",
            "",
            f"**Repository:** `{repository.path}`  ",
            f"**Branch:** `{repository.current_branch}`  ",
            f"**Analysis Date:** {format_display_date(now)}  ",
            "",
            "---",
            "",
            "## Repository Overview",
            "",
            f"- **Repository Name:** {repository.name}",
            f"- **Current Active Branch:** {repository.current_branch}",
            f"- **Total Commits Analyzed:** {len(commits):,}",
            f"- **Tracked Files in Tree:** {repository.total_files:,}",
            f"- **Active Contributors:** {repository.active_developers:,}",
            f"- **First Commit Date:** {format_display_date(repository.first_commit_date)}",
            f"- **Latest Commit Date:** {format_display_date(repository.latest_commit_date)}",
            f"- **History Age:** {repository.age_in_days()} days",
            f"- **Activity Cadence:** {repository.activity_level()}",
            "",
            "## Commit Statistics",
            "",
            f"- **Total Lines Added:** +{churn_metrics.get('total_additions', 0):,}",
            f"- **Total Lines Deleted:** -{churn_metrics.get('total_deletions', 0):,}",
            f"- **Gross Code Churn:** {churn_metrics.get('total_churn', 0):,} lines",
            f"- **Average Commit Size:** {churn_metrics.get('mean_commit_size', 0.0):.1f} lines",
            f"- **Median Commit Size:** {churn_metrics.get('median_commit_size', 0.0):.1f} lines",
        ]

        largest = churn_metrics.get("largest_commit")
        if largest:
            lines.append(
                f"- **Largest Single Commit:** `[{largest.get('hash')}]` "
                f"by {largest.get('author')} ({largest.get('churn'):,} lines touched)"
            )
        lines.append("")

        # Developer Activity section
        lines.extend([
            "## Developer Activity",
            "",
            "| Contributor | Commits | Additions | Deletions | Net Lines | Avg Size | Touched Files |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        sorted_devs = sorted(developers, key=lambda d: d.commit_count, reverse=True)
        for dev in sorted_devs:
            net = dev.lines_added - dev.lines_deleted
            lines.append(
                f"| {dev.name} | {dev.commit_count:,} | +{dev.lines_added:,} | "
                f"-{dev.lines_deleted:,} | {net:+,} | {dev.average_commit_size:.1f} | {dev.unique_files_count:,} |"
            )
        lines.append("")

        # Top Modified Files
        lines.extend([
            "## Top Modified Files",
            "",
            "| File Path | Modifications | Total Churn | Volatility |",
            "| :--- | :--- | :--- | :--- |",
        ])
        for entry in top_files[:10]:
            lines.append(
                f"| `{entry.get('file_path')}` | {entry.get('modification_count', 0)} | "
                f"{entry.get('total_changes', 0):,} | {entry.get('volatility_score', 0.0):.1f} |"
            )
        lines.append("")

        # Risky Files
        lines.extend([
            "## Risky Files",
            "",
            "| File Path | Risk Score | Risk Tier | Primary Drivers | Recommended Mitigation |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for r in top_risky:
            drivers = "; ".join(r.reasons[:2])
            lines.append(
                f"| `{r.file_path}` | {r.score:.1f} | **{r.level}** | {drivers} | {r.recommended_action} |"
            )
        lines.append("")

        # Unusual Commits
        lines.extend([
            "## Unusual Commits",
            "",
        ])
        if anomalies:
            lines.append(f"**{len(anomalies)} statistical outlier event(s) detected:**\n")
            for a in anomalies[:8]:
                lines.append(f"- **{a.metric}** `[{a.identifier}]`: {a.reason}")
        else:
            lines.append("No statistical anomalies detected within current configuration thresholds.")
        lines.append("")

        # Commit Classification
        lines.extend([
            "## Commit Classification",
            "",
            "| Intent Category | Commit Count | Share (%) |",
            "| :--- | :--- | :--- |",
        ])
        total_c = max(1, len(commits))
        for cat, count in classifications.items():
            pct = (count / total_c) * 100.0
            lines.append(f"| {cat} | {count:,} | {pct:.1f}% |")
        lines.append("")

        # Release Forecast
        lines.extend([
            "## Release Forecast",
            "",
        ])
        if prediction:
            lines.extend([
                f"- **Predicted Next-Period Churn:** ~{int(round(prediction.predicted_volume)):,} lines",
                f"- **Velocity Slope Coefficient:** {prediction.coefficient:+.2f} lines/period",
                f"- **Model Mean Absolute Error (MAE):** ±{prediction.mae:.1f} lines",
                f"- **Historical Intervals Analyzed:** {prediction.periods_count}",
                f"- *Note:* {prediction.confidence_note}",
            ])
        else:
            lines.append("Insufficient historical time series data to generate linear regression forecast.")
        lines.append("")

        # Repository Health
        lines.extend([
            "## Repository Health",
            "",
            f"- **Repository Health Score:** **{repository.health_score:.1f} / 100**",
            f"- **Overall Release Risk Tier:** **{release_risk.level}** ({release_risk.overall_score:.1f}/100)",
            f"- **Summary:** {release_risk.summary_text}",
            "",
            "## Recommended Developer Actions",
            "",
            "The following are heuristic engineering suggestions intended to guide peer review and automated testing priorities:",
            "",
        ])

        if top_risky:
            lines.append("1. **Targeted Code Reviews:** Focus peer review on elevated risk files:")
            for r in top_risky[:4]:
                lines.append(f"   - `{r.file_path}` (Score: {r.score:.0f}, Tier: {r.level})")
        
        if anomalies:
            lines.append("2. **Inspect Large Burst Commits:** Review outsized single-commit diffs to confirm absence of unintentional file additions or vendor dependencies.")

        if release_risk.level in ("HIGH", "CRITICAL"):
            lines.append("3. **Regression Test Suites:** Run end-to-end regression test suites covering the core modified subsystems before cutting the next release tag.")
        else:
            lines.append("3. **Standard CI Verification:** Standard test suite passing is recommended; codebase stability indicators are within normal parameters.")

        lines.append("")

        try:
            with open(out_path, mode="w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            return out_path
        except Exception as err:
            raise ReportGenerationError(f"Failed to write Markdown report: {err}") from err

    def generate_summary_csv(
        self,
        repository: Repository,
        commits: Sequence[Commit],
        churn_metrics: Dict[str, Any],
        release_risk: ReleaseRisk,
        custom_filename: str = "repository_summary.csv",
    ) -> Path:
        """Render executive repository summary CSV table."""
        out_path = self.output_dir / custom_filename
        rows = [
            {"Metric": "Repository Name", "Value": repository.name},
            {"Metric": "Active Branch", "Value": repository.current_branch},
            {"Metric": "Total Commits", "Value": len(commits)},
            {"Metric": "Tracked Files", "Value": repository.total_files},
            {"Metric": "Active Contributors", "Value": repository.active_developers},
            {"Metric": "Repository Health Score", "Value": f"{repository.health_score:.1f}"},
            {"Metric": "Release Risk Level", "Value": release_risk.level},
            {"Metric": "Release Risk Score", "Value": f"{release_risk.overall_score:.1f}"},
            {"Metric": "Total Additions", "Value": churn_metrics.get("total_additions", 0)},
            {"Metric": "Total Deletions", "Value": churn_metrics.get("total_deletions", 0)},
            {"Metric": "Total Code Churn", "Value": churn_metrics.get("total_churn", 0)},
            {"Metric": "Mean Commit Churn", "Value": churn_metrics.get("mean_commit_size", 0.0)},
            {"Metric": "Median Commit Churn", "Value": churn_metrics.get("median_commit_size", 0.0)},
        ]

        try:
            with open(out_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["Metric", "Value"])
                writer.writeheader()
                writer.writerows(rows)
            return out_path
        except Exception as err:
            raise ReportGenerationError(f"Failed to write summary CSV: {err}") from err
