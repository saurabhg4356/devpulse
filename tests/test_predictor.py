"""Unit tests for ReleasePredictor using LinearRegression."""

from datetime import datetime, timezone, timedelta
import pytest

from models.commit import Commit
from models.exceptions import InsufficientDataError
from services.release_predictor import ReleasePredictor


class TestReleasePredictor:
    """Verify linear regression code churn trend forecasting."""

    def test_predict_with_sufficient_history(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Create commits spanning 5 distinct weekly periods with increasing churn
        # Week 1: 100, Week 2: 150, Week 3: 200, Week 4: 250, Week 5: 300
        commits: list[Commit] = []
        for i in range(5):
            c_date = base + timedelta(days=i * 7)
            commits.append(
                Commit(
                    commit_hash=f"{i+1}" * 40,
                    author="Tester",
                    author_email="test@example.com",
                    commit_date=c_date,
                    message=f"commit for week {i+1}",
                    files_changed=["file.py"],
                    insertions=100 + (i * 50),
                    deletions=0,
                )
            )

        predictor = ReleasePredictor()
        result = predictor.predict_next_period_churn(commits, period_freq="W")

        assert result.periods_count >= 3
        assert result.predicted_volume > 0
        assert result.coefficient > 0  # Upward trend
        assert result.mae is not None
        assert "predicted" in result.summary().lower()

    def test_predict_insufficient_history_raises(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Only 1 commit in 1 period
        commits = [
            Commit("1" * 40, "A", "a@a.com", base, "msg", ["a.py"], 50, 0),
        ]
        predictor = ReleasePredictor()
        with pytest.raises(InsufficientDataError):
            predictor.predict_next_period_churn(commits, period_freq="W")

    def test_predict_empty_commits_raises(self) -> None:
        predictor = ReleasePredictor()
        with pytest.raises(InsufficientDataError):
            predictor.predict_next_period_churn([], period_freq="W")
