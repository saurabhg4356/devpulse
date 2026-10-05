"""Unit tests for DevPulse domain models and custom exceptions."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from models.commit import Commit
from models.developer import Developer
from models.exceptions import (
    AnalysisError,
    ClassificationError,
    DevPulseError,
    GitCommandError,
    InsufficientDataError,
    InvalidCommitError,
    InvalidRepositoryError,
    PredictionError,
    ReportGenerationError,
    StorageError,
)
from models.file_change import FileChange
from models.repository import Repository
from models.risk import ReleaseRisk, RiskResult


class TestExceptions:
    """Verify custom exception hierarchy and formatting."""

    def test_custom_exception_hierarchy(self) -> None:
        errors = [
            InvalidRepositoryError("Bad repo"),
            GitCommandError("Git failed", command="git log", exit_code=128, stderr="fatal error"),
            InvalidCommitError("Bad commit"),
            AnalysisError("Analysis fault"),
            InsufficientDataError("Need more data"),
            PredictionError("Regression failed"),
            ClassificationError("Model not ready"),
            ReportGenerationError("Report failed"),
            StorageError("Disk error"),
        ]
        for err in errors:
            assert isinstance(err, DevPulseError)
            assert isinstance(err, Exception)

    def test_git_command_error_details(self) -> None:
        err = GitCommandError("Command failed", command="git log", exit_code=1, stderr="Not a git repo")
        assert "Not a git repo" in str(err)
        assert err.command == "git log"
        assert err.exit_code == 1


class TestCommitModel:
    """Verify Commit model encapsulation, comparison, and serialization."""

    def test_commit_initialization_and_properties(self) -> None:
        dt = datetime(2026, 2, 1, 14, 0, 0, tzinfo=timezone.utc)
        c = Commit(
            commit_hash="1122334455667788990011223344556677889900",
            author="Dev One",
            author_email="dev1@example.com",
            commit_date=dt,
            message="feat: add logging",
            files_changed=["app.py", "utils.py"],
            insertions=50,
            deletions=10,
        )
        assert c.short_hash == "1122334"
        assert c.author == "Dev One"
        assert c.author_email == "dev1@example.com"
        assert c.total_changes == 60
        assert c.file_count == 2
        assert "app.py" in c.files_changed

    def test_commit_invalid_hash_raises(self) -> None:
        with pytest.raises(InvalidCommitError):
            Commit(
                commit_hash="not-a-valid-hash-!@#$",
                author="A",
                author_email="a@b.com",
                commit_date=datetime.now(timezone.utc),
                message="test",
            )

    def test_commit_chronological_comparison(self) -> None:
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 5, tzinfo=timezone.utc)
        c1 = Commit(
            commit_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            author="A",
            author_email="a@b.com",
            commit_date=t1,
            message="First",
        )
        c2 = Commit(
            commit_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            author="B",
            author_email="b@b.com",
            commit_date=t2,
            message="Second",
        )
        assert c1 < c2
        assert c2 > c1
        assert c1 <= c2
        assert c1 < t2
        assert sorted([c2, c1]) == [c1, c2]

    def test_commit_to_and_from_dict(self) -> None:
        dt = datetime(2026, 3, 15, 12, 30, 0, tzinfo=timezone.utc)
        c = Commit(
            commit_hash="cccccccccccccccccccccccccccccccccccccccc",
            author="Charlie",
            author_email="c@example.com",
            commit_date=dt,
            message="test commit",
            files_changed=["a.txt"],
            insertions=10,
            deletions=2,
            classification="Testing",
            risk_score=45.5,
        )
        data = c.to_dict()
        assert data["commit_hash"] == "cccccccccccccccccccccccccccccccccccccccc"
        assert data["classification"] == "Testing"
        assert data["risk_score"] == 45.5

        reconstructed = Commit.from_dict(data)
        assert reconstructed.commit_hash == c.commit_hash
        assert reconstructed.classification == "Testing"
        assert reconstructed.total_changes == 12


class TestFileChangeModel:
    """Verify FileChange churn and validations."""

    def test_file_change_properties(self) -> None:
        fc = FileChange(
            file_path="src\\deep\\module.py",
            commit_hash="1234567890abcdef1234567890abcdef12345678",
            change_type="modified",
            insertions=35,
            deletions=15,
        )
        assert fc.file_path == "src/deep/module.py"
        assert fc.total_changes == 50
        assert fc.churn == 50
        assert fc.net_change == 20
        assert fc.change_type == "modified"

    def test_file_change_invalid_path(self) -> None:
        with pytest.raises(ValueError):
            FileChange(file_path="", commit_hash="1234567890abcdef1234567890abcdef12345678")


class TestDeveloperModel:
    """Verify Developer metrics and aggregation."""

    def test_developer_accumulation(self) -> None:
        dev = Developer(name="Alice", email="alice@test.com")
        assert dev.commit_count == 0
        assert dev.average_commit_size == 0.0

        dev.add_commit(insertions=100, deletions=20, files={"a.py", "b.py"})
        dev.add_commit(insertions=40, deletions=0, files={"b.py", "c.py"})

        assert dev.commit_count == 2
        assert dev.lines_added == 140
        assert dev.lines_deleted == 20
        assert dev.total_changes == 160
        assert dev.average_commit_size == 80.0
        assert dev.unique_files_count == 3
        assert "Alice" in dev.summary()


class TestRiskModels:
    """Verify RiskResult score clamping and comparisons."""

    def test_risk_result_clamping_and_sorting(self) -> None:
        r1 = RiskResult(file_path="hotspot.py", score=120.0, level="CRITICAL")
        r2 = RiskResult(file_path="normal.py", score=-10.0, level="LOW")
        assert r1.score == 100.0
        assert r2.score == 0.0
        assert r1 > r2
        assert r2 < r1

    def test_release_risk_creation(self) -> None:
        rr = ReleaseRisk(overall_score=75.4, level="HIGH", top_risk_drivers=["api.py"])
        assert rr.level == "HIGH"
        assert rr.overall_score == 75.4


class TestRepositoryModel:
    """Verify Repository encapsulation and activity metrics."""

    def test_repository_metrics(self, tmp_path: Path) -> None:
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 31, tzinfo=timezone.utc)
        repo = Repository(
            repository_path=tmp_path,
            repository_name="sample-repo",
            current_branch="main",
            total_commits=50,
            total_files=20,
            active_developers=4,
            first_commit_date=t1,
            latest_commit_date=t2,
        )
        assert repo.name == "sample-repo"
        assert repo.age_in_days() == 30
        assert repo.activity_level() in ("HIGH", "MODERATE", "LOW", "DORMANT")
        summary = repo.summary()
        assert summary["total_commits"] == 50
