"""Unit tests for analytics, churn metrics, file volatility, and polymorphic analyzers."""

from pathlib import Path
from models.commit import Commit
from services.analytics import (
    calculate_repository_health_score,
    compute_churn_metrics,
    compute_file_volatility,
)
from services.analyzer import Analyzer
from services.commit_analyzer import CommitAnalyzer
from services.file_analyzer import FileAnalyzer
from services.repository_analyzer import RepositoryAnalyzer


class TestChurnAnalytics:
    """Verify pandas and NumPy code churn statistical aggregations."""

    def test_churn_metrics_calculation(self, sample_commits: list[Commit]) -> None:
        metrics = compute_churn_metrics(sample_commits)
        assert metrics["total_commits"] == len(sample_commits)
        assert metrics["total_additions"] == 285
        assert metrics["total_deletions"] == 52
        assert metrics["total_churn"] == 337
        assert metrics["mean_commit_size"] > 0
        assert metrics["median_commit_size"] > 0
        assert metrics["largest_commit"] is not None
        assert "hash" in metrics["largest_commit"]

    def test_churn_metrics_empty(self) -> None:
        metrics = compute_churn_metrics([])
        assert metrics["total_commits"] == 0
        assert metrics["total_churn"] == 0
        assert metrics["largest_commit"] is None


class TestFileVolatility:
    """Verify file volatility heuristic calculations."""

    def test_volatility_zero_commits(self) -> None:
        stat = {"modification_count": 0, "total_changes": 0}
        assert compute_file_volatility(stat, total_commits=0) == 0.0

    def test_volatility_hotspot_vs_stable(self) -> None:
        hotspot_stat = {
            "modification_count": 10,
            "total_changes": 1500,
            "authors": {"alice@a.com", "bob@b.com", "charlie@c.com"},
        }
        stable_stat = {
            "modification_count": 1,
            "total_changes": 5,
            "authors": {"alice@a.com"},
        }
        vol_hot = compute_file_volatility(hotspot_stat, total_commits=15)
        vol_stable = compute_file_volatility(stable_stat, total_commits=15)
        assert vol_hot > vol_stable
        assert 0.0 <= vol_hot <= 100.0


class TestRepositoryHealthScore:
    """Verify repository health score deductions and category assignment."""

    def test_clean_repo_high_health(self, sample_commits: list[Commit]) -> None:
        score, risk_tier = calculate_repository_health_score(
            commits=sample_commits,
            anomalies_count=0,
            high_risk_files_count=0,
            total_files=10,
        )
        assert score >= 80.0
        assert risk_tier == "LOW"

    def test_high_risk_repo_health_deductions(self, sample_commits: list[Commit]) -> None:
        score, risk_tier = calculate_repository_health_score(
            commits=sample_commits,
            anomalies_count=4,
            high_risk_files_count=8,
            total_files=10,
        )
        assert score < 70.0
        assert risk_tier in ("MEDIUM", "HIGH", "CRITICAL")


class TestPolymorphicAnalyzers:
    """Verify OOP Inheritance and Polymorphic analyze() interface."""

    def test_polymorphic_analyzers_execution(self, sample_commits: list[Commit], tmp_path: Path) -> None:
        analyzers: list[Analyzer] = [
            RepositoryAnalyzer(),
            CommitAnalyzer(),
            FileAnalyzer(),
        ]

        # Polymorphic orchestration
        for analyzer in analyzers:
            assert isinstance(analyzer, Analyzer)
            target = {
                "repo_path": tmp_path,
                "commits": sample_commits,
                "total_files": 5,
                "branch": "main",
            }
            res = analyzer.analyze(target)
            assert isinstance(res, dict)
            assert len(res) > 0
