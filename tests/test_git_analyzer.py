"""Integration tests for GitAnalyzer with deterministic local Git repositories."""

from pathlib import Path
import subprocess
import pytest

from models.exceptions import GitCommandError, InvalidRepositoryError
from services.git_analyzer import GitAnalyzer


class TestGitAnalyzer:
    """Verify safe Git extraction on local repositories."""

    def test_git_analyzer_on_valid_repo(self, temp_git_repo: Path) -> None:
        analyzer = GitAnalyzer(temp_git_repo)
        assert analyzer.repository_path == temp_git_repo.resolve()
        
        branch = analyzer.get_current_branch()
        assert branch in ("main", "master")

        total_files = analyzer.get_total_files()
        assert total_files >= 2  # calc.py, README.md, test_calc.py

    def test_git_analyzer_invalid_repo_raises(self, tmp_path: Path) -> None:
        not_a_repo = tmp_path / "plain_dir"
        not_a_repo.mkdir()
        with pytest.raises(InvalidRepositoryError):
            GitAnalyzer(not_a_repo)

    def test_forbidden_mutating_command_raises(self, temp_git_repo: Path) -> None:
        analyzer = GitAnalyzer(temp_git_repo)
        with pytest.raises(GitCommandError) as exc_info:
            analyzer._run_git(["commit", "-m", "illegal"])
        assert "forbidden" in str(exc_info.value).lower()

    def test_extract_commits_chronological(self, temp_git_repo: Path) -> None:
        analyzer = GitAnalyzer(temp_git_repo)
        commits = analyzer.extract_commits()
        assert len(commits) == 5
        # Verify chronological sorting (oldest first)
        for i in range(len(commits) - 1):
            assert commits[i].commit_date <= commits[i + 1].commit_date

    def test_extract_commits_limit(self, temp_git_repo: Path) -> None:
        analyzer = GitAnalyzer(temp_git_repo)
        commits = analyzer.extract_commits(max_count=2)
        assert len(commits) == 2

    def test_extract_commits_author_filter(self, temp_git_repo: Path) -> None:
        analyzer = GitAnalyzer(temp_git_repo)
        commits = analyzer.extract_commits(author="Test Committer")
        assert len(commits) == 5

        empty = analyzer.extract_commits(author="NonExistentPerson")
        assert len(empty) == 0

    def test_empty_git_repository_graceful(self, tmp_path: Path) -> None:
        empty_repo = tmp_path / "empty_repo"
        empty_repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=str(empty_repo), check=True, capture_output=True)

        analyzer = GitAnalyzer(empty_repo)
        commits = analyzer.extract_commits()
        assert commits == []
