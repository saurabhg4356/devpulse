"""CommitAnalyzer subclass for analyzing commit series, churn distribution, and temporal dynamics."""

from typing import Any, Dict, Sequence
from models.commit import Commit
from services.analytics import compute_churn_metrics
from services.analyzer import Analyzer


class CommitAnalyzer(Analyzer):
    """Analyzes commit sequence metrics, code churn volume, and commit dynamics."""

    def __init__(self, name: str = "CommitAnalyzer") -> None:
        super().__init__(name)

    def analyze(self, target: Any) -> Dict[str, Any]:
        """Perform polymorphic commit history analysis.
        
        Args:
            target: Sequence of Commit objects (or dict with 'commits' key).
            
        Returns:
            Dictionary containing code churn statistics and temporal patterns.
        """
        commits: Sequence[Commit] = (
            target.get("commits", []) if isinstance(target, dict) else target
        )

        churn_metrics = compute_churn_metrics(commits)
        
        # Calculate commit author frequencies
        author_counts: Dict[str, int] = {}
        for c in commits:
            name = c.author or "Unknown"
            author_counts[name] = author_counts.get(name, 0) + 1

        return {
            "churn_metrics": churn_metrics,
            "total_commits": len(commits),
            "author_commit_distribution": author_counts,
            "mean_commit_size": churn_metrics["mean_commit_size"],
            "median_commit_size": churn_metrics["median_commit_size"],
            "largest_commit": churn_metrics["largest_commit"],
        }
