"""RepositoryAnalyzer subclass for analyzing repository-level health and metrics."""

from pathlib import Path
from typing import Any, Dict, Optional, Sequence
from models.commit import Commit
from models.repository import Repository
from services.analytics import calculate_repository_health_score
from services.analyzer import Analyzer


class RepositoryAnalyzer(Analyzer):
    """Analyzes high-level repository attributes, activity cadence, and health metrics."""

    def __init__(self, name: str = "RepositoryAnalyzer") -> None:
        super().__init__(name)

    def analyze(self, target: Any) -> Dict[str, Any]:
        """Perform polymorphic repository-level analysis.
        
        Args:
            target: Dictionary with keys:
                - 'repo_path': Path to repository
                - 'commits': Sequence[Commit]
                - 'total_files': int
                - 'branch': str
                - 'anomalies_count': int (optional)
                - 'high_risk_files_count': int (optional)
                
        Returns:
            Dictionary containing Repository model instance and health indicators.
        """
        repo_path = Path(target.get("repo_path", "."))
        commits: Sequence[Commit] = target.get("commits", [])
        total_files: int = int(target.get("total_files", 0))
        branch: str = target.get("branch", "main")
        anomalies_count: int = int(target.get("anomalies_count", 0))
        high_risk_files_count: int = int(target.get("high_risk_files_count", 0))

        first_date = commits[0].commit_date if commits else None
        latest_date = commits[-1].commit_date if commits else None
        unique_authors = len({c.author_email or c.author for c in commits})

        health_score, release_risk = calculate_repository_health_score(
            commits=commits,
            anomalies_count=anomalies_count,
            high_risk_files_count=high_risk_files_count,
            total_files=total_files,
        )

        repo_model = Repository(
            repository_path=repo_path,
            repository_name=repo_path.name,
            current_branch=branch,
            total_commits=len(commits),
            total_files=total_files,
            active_developers=unique_authors,
            first_commit_date=first_date,
            latest_commit_date=latest_date,
            health_score=health_score,
        )

        return {
            "repository": repo_model,
            "health_score": health_score,
            "release_risk": release_risk,
            "age_in_days": repo_model.age_in_days(),
            "activity_level": repo_model.activity_level(),
            "summary": repo_model.summary(),
        }
