"""Shared pytest fixtures for DevPulse test suite.

Provides mock domain models and deterministic local Git repository fixtures.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess
from typing import List
import pytest

from models.commit import Commit
from models.developer import Developer
from models.file_change import FileChange
from models.risk import RiskResult


@pytest.fixture
def sample_commits() -> List[Commit]:
    """Provide a deterministic chronological list of Commit objects."""
    base_time = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return [
        Commit(
            commit_hash="11111114e5f6a1b2c3d4e5f6a1b2c3d4e5f60001",
            author="Alice Developer",
            author_email="alice@example.com",
            commit_date=base_time,
            message="feat: initial project structure and entry point",
            files_changed=["main.py", "README.md"],
            insertions=120,
            deletions=0,
            classification="Feature",
        ),
        Commit(
            commit_hash="22222224e5f6a1b2c3d4e5f6a1b2c3d4e5f60002",
            author="Bob Engineer",
            author_email="bob@example.com",
            commit_date=base_time + timedelta(days=7),
            message="fix: resolve null pointer exception in auth service",
            files_changed=["auth/service.py"],
            insertions=15,
            deletions=5,
            classification="Bug Fix",
        ),
        Commit(
            commit_hash="33333334e5f6a1b2c3d4e5f6a1b2c3d4e5f60003",
            author="Alice Developer",
            author_email="alice@example.com",
            commit_date=base_time + timedelta(days=14),
            message="refactor: decouple database connection pool",
            files_changed=["database/connection.py", "auth/service.py"],
            insertions=40,
            deletions=35,
            classification="Refactor",
        ),
        Commit(
            commit_hash="44444444e5f6a1b2c3d4e5f6a1b2c3d4e5f60004",
            author="Charlie QA",
            author_email="charlie@example.com",
            commit_date=base_time + timedelta(days=21),
            message="test: add unit tests for auth and database modules",
            files_changed=["tests/test_auth.py"],
            insertions=85,
            deletions=2,
            classification="Testing",
        ),
        Commit(
            commit_hash="55555554e5f6a1b2c3d4e5f6a1b2c3d4e5f60005",
            author="Bob Engineer",
            author_email="bob@example.com",
            commit_date=base_time + timedelta(days=28),
            message="perf: optimize sql queries in user repository",
            files_changed=["database/connection.py"],
            insertions=25,
            deletions=10,
            classification="Performance",
        ),
    ]


@pytest.fixture
def sample_developers() -> List[Developer]:
    """Provide sample Developer instances."""
    d1 = Developer(name="Alice Developer", email="alice@example.com", commit_count=2, lines_added=160, lines_deleted=35)
    d1.files_changed.update(["main.py", "README.md", "database/connection.py", "auth/service.py"])
    d2 = Developer(name="Bob Engineer", email="bob@example.com", commit_count=2, lines_added=40, lines_deleted=15)
    d2.files_changed.update(["auth/service.py", "database/connection.py"])
    return [d1, d2]


@pytest.fixture
def sample_file_changes() -> List[FileChange]:
    """Provide sample FileChange instances."""
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return [
        FileChange(
            file_path="src/service.py",
            commit_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f60001",
            change_type="added",
            insertions=100,
            deletions=0,
            timestamp=ts,
        ),
        FileChange(
            file_path="src/service.py",
            commit_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f60002",
            change_type="modified",
            insertions=20,
            deletions=10,
            timestamp=ts + timedelta(days=2),
        ),
    ]


@pytest.fixture
def sample_risk_results() -> List[RiskResult]:
    """Provide sample RiskResult evaluations."""
    return [
        RiskResult(
            file_path="src/services/payment.py",
            score=91.0,
            level="CRITICAL",
            reasons=["High recent modification frequency", "Large recent code churn"],
            recommended_action="Immediate peer review required.",
        ),
        RiskResult(
            file_path="src/auth/service.py",
            score=84.0,
            level="CRITICAL",
            reasons=["Multiple developers modified this file", "Recent modifications"],
            recommended_action="Review recent changes and run regression tests.",
        ),
        RiskResult(
            file_path="src/order/controller.py",
            score=55.0,
            level="MEDIUM",
            reasons=["Moderate code churn"],
            recommended_action="Standard code review recommended.",
        ),
        RiskResult(
            file_path="README.md",
            score=12.0,
            level="LOW",
            reasons=["Standard modification volume and historical stability"],
            recommended_action="Low risk.",
        ),
    ]


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Initialize a deterministic temporary Git repository with multiple commits.
    
    Creates real commit history with branches, files, and diffs for integration testing.
    """
    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Safe git helper inside temp dir
    def git(*args: str) -> None:
        cmd = ["git"] + list(args)
        subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )

    # Configure local git
    git("init", "-b", "main")
    git("config", "user.name", "Test Committer")
    git("config", "user.email", "committer@example.com")
    git("config", "commit.gpgSign", "false")

    # Commit 1: Initial files
    (repo / "README.md").write_text("# Test Repository\nInitial docs.\n", encoding="utf-8")
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "feat: initial commit with basic calculator")

    # Commit 2: Add feature
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8")
    git("add", "calc.py")
    git("commit", "-m", "feat: implement subtraction function")

    # Commit 3: Bug fix
    (repo / "calc.py").write_text("def add(a, b):\n    return int(a) + int(b)\n\ndef sub(a, b):\n    return a - b\n", encoding="utf-8")
    git("add", "calc.py")
    git("commit", "-m", "fix: cast inputs to integer in add function")

    # Commit 4: Add test
    (repo / "test_calc.py").write_text("from calc import add\ndef test_add(): assert add(1, 2) == 3\n", encoding="utf-8")
    git("add", "test_calc.py")
    git("commit", "-m", "test: add unit test for addition")

    # Commit 5: Large refactor
    extra_lines = "\n".join([f"# helper line {i}" for i in range(50)])
    (repo / "calc.py").write_text(f"def add(a, b):\n    return a + b\n{extra_lines}\n", encoding="utf-8")
    git("add", "calc.py")
    git("commit", "-m", "refactor: expand calculator module utilities")

    return repo
