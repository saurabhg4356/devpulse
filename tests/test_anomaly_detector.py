"""Unit tests for statistical AnomalyDetector."""

from datetime import datetime, timezone, timedelta
import pytest

from models.commit import Commit
from services.anomaly_detector import AnomalyDetector


class TestAnomalyDetector:
    """Verify Z-score and statistical anomaly detection."""

    def test_detect_commit_anomalies_finds_outlier(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # 5 normal commits (~20-40 lines) and 1 extreme outlier (+3,000 lines)
        commits = [
            Commit("1" * 40, "A", "a@a.com", base + timedelta(days=1), "c1", ["a.py"], 20, 5),
            Commit("2" * 40, "A", "a@a.com", base + timedelta(days=2), "c2", ["a.py"], 25, 10),
            Commit("3" * 40, "A", "a@a.com", base + timedelta(days=3), "c3", ["b.py"], 30, 5),
            Commit("4" * 40, "A", "a@a.com", base + timedelta(days=4), "c4", ["a.py"], 15, 5),
            Commit("5" * 40, "A", "a@a.com", base + timedelta(days=5), "c5", ["b.py"], 20, 10),
            Commit("6" * 40, "B", "b@b.com", base + timedelta(days=6), "c6", ["c.py"], 3500, 200),
        ]
        detector = AnomalyDetector()
        anomalies = detector.detect_commit_anomalies(commits)
        assert len(anomalies) >= 1
        outlier = anomalies[0]
        assert outlier.identifier == "6666666"
        assert outlier.z_score >= 2.0
        assert "significantly above" in outlier.reason.lower()

    def test_zero_standard_deviation_handled(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # All commits have identical churn: 50 lines
        commits = [
            Commit(f"{i}" * 40, "A", "a@a.com", base + timedelta(days=i), f"c{i}", ["a.py"], 50, 0)
            for i in range(1, 6)
        ]
        detector = AnomalyDetector()
        # Must not raise ZeroDivisionError
        anomalies = detector.detect_commit_anomalies(commits)
        assert anomalies == []

    def test_insufficient_samples_returns_empty(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        commits = [
            Commit("1" * 40, "A", "a@a.com", base, "c1", ["a.py"], 50, 0),
        ]
        detector = AnomalyDetector()
        assert detector.detect_commit_anomalies(commits) == []
        assert detector.detect_file_modification_anomalies(commits) == []
