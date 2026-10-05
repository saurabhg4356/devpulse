"""FileAnalyzer subclass for calculating file-level churn, volatility, and hotspot metrics."""

from typing import Any, Dict, List, Sequence
from models.commit import Commit
from services.analytics import compute_file_volatility
from services.analyzer import Analyzer
from services.dsa_utils import build_file_stats_map, get_top_changed_files


class FileAnalyzer(Analyzer):
    """Analyzes file modification patterns, volatility heuristics, and hotspot concentration."""

    def __init__(self, name: str = "FileAnalyzer") -> None:
        super().__init__(name)

    def analyze(self, target: Any) -> Dict[str, Any]:
        """Perform polymorphic file modification analysis.
        
        Args:
            target: Sequence of Commit objects (or dict with 'commits' key).
            
        Returns:
            Dictionary containing file statistics map, volatility scores, and top modified files.
        """
        commits: Sequence[Commit] = (
            target.get("commits", []) if isinstance(target, dict) else target
        )
        total_commits = len(commits)

        # Build file_path -> stats Hash Map (O(1) average lookup)
        file_stats_map = build_file_stats_map(commits)

        # Compute volatility score for each file
        file_volatility: Dict[str, float] = {}
        for path, stats in file_stats_map.items():
            vol = compute_file_volatility(stats, total_commits)
            file_volatility[path] = vol
            stats["volatility_score"] = vol

        # Use heapq for top-10 modified files in O(N log K)
        top_modified = get_top_changed_files(file_stats_map, k=10)

        return {
            "total_tracked_files_modified": len(file_stats_map),
            "file_stats_map": file_stats_map,
            "file_volatility": file_volatility,
            "top_modified_files": top_modified,
        }
