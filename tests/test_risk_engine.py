"""Unit tests for RiskEngine scoring, explanations, and thresholds."""

from datetime import datetime, timezone
import pytest

from config.settings import DevPulseConfig, RiskThresholds
from models.commit import Commit
from services.risk_engine import RiskEngine


class TestRiskEngine:
    """Verify multi-factor risk assessment and recommendations."""

    def test_evaluate_file_high_risk(self) -> None:
        engine = RiskEngine()
        stats = {
            "modification_count": 15,
            "total_changes": 2500,
            "authors": {"alice@a.com", "bob@b.com", "charlie@c.com", "dave@d.com"},
            "latest_commit_date": datetime.now(timezone.utc),
            "volatility_score": 85.0,
        }
        res = engine.evaluate_file("src/payment.py", stats, total_repo_commits=20)
        assert res.score >= 60.0
        assert res.level in ("HIGH", "CRITICAL")
        assert len(res.reasons) >= 2
        assert "regression" in res.recommended_action.lower() or "review" in res.recommended_action.lower()

    def test_evaluate_file_low_risk(self) -> None:
        engine = RiskEngine()
        stats = {
            "modification_count": 1,
            "total_changes": 10,
            "authors": {"alice@a.com"},
            "latest_commit_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "volatility_score": 10.0,
        }
        res = engine.evaluate_file("docs/readme.md", stats, total_repo_commits=100)
        assert res.score <= 30.0
        assert res.level == "LOW"

    def test_evaluate_repository(self, sample_commits: list[Commit]) -> None:
        engine = RiskEngine()
        file_risks, release_risk = engine.evaluate_repository(sample_commits)
        assert len(file_risks) > 0
        assert 0.0 <= release_risk.overall_score <= 100.0
        assert release_risk.level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert isinstance(release_risk.summary_text, str)

    def test_custom_thresholds(self) -> None:
        custom_cfg = DevPulseConfig(
            risk_thresholds=RiskThresholds(low_max=10.0, medium_max=30.0, high_max=50.0)
        )
        engine = RiskEngine(config=custom_cfg)
        stats = {
            "modification_count": 2,
            "total_changes": 100,
            "authors": {"a@a.com"},
            "latest_commit_date": datetime.now(timezone.utc),
        }
        res = engine.evaluate_file("mod.py", stats, total_repo_commits=10)
        # Check custom category mapping
        assert res.level in ("MEDIUM", "HIGH", "CRITICAL")
