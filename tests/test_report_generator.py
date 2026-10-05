"""Unit tests for ReportGenerator and Visualizer."""

from datetime import datetime, timezone
from pathlib import Path
import pytest

from models.commit import Commit
from models.developer import Developer
from models.repository import Repository
from models.risk import ReleaseRisk, RiskResult
from services.analytics import compute_churn_metrics
from services.report_generator import ReportGenerator
from services.visualizer import Visualizer


class TestReportGenerator:
    """Verify Markdown and CSV report generation."""

    def test_markdown_report_contains_all_sections(
        self,
        tmp_path: Path,
        sample_commits: list[Commit],
        sample_developers: list[Developer],
        sample_risk_results: list[RiskResult],
    ) -> None:
        generator = ReportGenerator(output_dir=tmp_path)
        repo = Repository(
            repository_path=tmp_path,
            repository_name="test-repo",
            current_branch="main",
            total_commits=len(sample_commits),
            total_files=5,
            active_developers=2,
            first_commit_date=sample_commits[0].commit_date,
            latest_commit_date=sample_commits[-1].commit_date,
            health_score=85.0,
        )
        churn_metrics = compute_churn_metrics(sample_commits)
        release_risk = ReleaseRisk(overall_score=45.0, level="MEDIUM", summary_text="Moderate risk")
        classifications = {"Feature": 2, "Bug Fix": 1, "Refactor": 1, "Testing": 1}

        md_path = generator.generate_markdown_report(
            repository=repo,
            commits=sample_commits,
            churn_metrics=churn_metrics,
            developers=sample_developers,
            top_files=[{"file_path": "main.py", "modification_count": 5, "total_changes": 100, "volatility_score": 50.0}],
            file_risks=sample_risk_results,
            release_risk=release_risk,
            anomalies=[],
            classifications=classifications,
            prediction=None,
        )

        assert md_path.exists()
        content = md_path.read_text(encoding="utf-8")

        # Verify all mandatory sections from specification
        assert "# DevPulse Repository Report" in content
        assert "## Repository Overview" in content
        assert "## Commit Statistics" in content
        assert "## Developer Activity" in content
        assert "## Top Modified Files" in content
        assert "## Risky Files" in content
        assert "## Unusual Commits" in content
        assert "## Commit Classification" in content
        assert "## Release Forecast" in content
        assert "## Repository Health" in content
        assert "## Recommended Developer Actions" in content

    def test_summary_csv_generation(
        self,
        tmp_path: Path,
        sample_commits: list[Commit],
    ) -> None:
        generator = ReportGenerator(output_dir=tmp_path)
        repo = Repository(repository_path=tmp_path, total_commits=len(sample_commits))
        churn = compute_churn_metrics(sample_commits)
        risk = ReleaseRisk(overall_score=30.0, level="LOW")

        csv_path = generator.generate_summary_csv(
            repository=repo,
            commits=sample_commits,
            churn_metrics=churn,
            release_risk=risk,
        )
        assert csv_path.exists()
        content = csv_path.read_text(encoding="utf-8")
        assert "Repository Health Score" in content
        assert "Release Risk Level" in content


class TestVisualizer:
    """Verify Matplotlib headless chart generation."""

    def test_generate_charts(
        self,
        tmp_path: Path,
        sample_commits: list[Commit],
        sample_developers: list[Developer],
        sample_risk_results: list[RiskResult],
    ) -> None:
        visualizer = Visualizer(output_dir=tmp_path)
        top_files = [{"file_path": "src/app.py", "modification_count": 10, "total_changes": 500}]

        charts = visualizer.generate_all_charts(
            commits=sample_commits,
            file_risks=sample_risk_results,
            top_files=top_files,
            developers=sample_developers,
            prediction=None,
        )

        assert "commit_activity" in charts
        assert "code_churn" in charts
        assert "top_modified_files" in charts
        assert "risk_distribution" in charts
        assert "developer_activity" in charts

        for name, path in charts.items():
            assert path.exists(), f"Chart {name} was not saved at {path}"
            assert path.stat().st_size > 0, f"Chart {name} file is empty"
