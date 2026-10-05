"""Data Structures and Algorithms (DSA) utilities for DevPulse.

Demonstrates production implementations of:
1. Hash Maps (Dictionary indexing for O(1) average lookups)
2. Heap / Priority Queue (heapq.nlargest for O(N log K) top-K selection)
3. Binary Search (bisect for O(log N) chronological date-range slicing)
4. Stack / LIFO (AnalysisHistoryStack for undoing filter states)
"""

import bisect
from datetime import datetime
import heapq
from typing import Any, Callable, Dict, Generic, List, Optional, Sequence, TypeVar, Union

from models.commit import Commit
from models.developer import Developer
from models.exceptions import AnalysisError
from models.risk import RiskResult

T = TypeVar("T")


# ============================================================================
# 1. HASH MAP INDEXING (Average O(1) lookups)
# ============================================================================

def build_commit_map(commits: Sequence[Commit]) -> Dict[str, Commit]:
    """Index commits by their unique 40-character SHA-1 hash.
    
    Complexity:
        Construction: O(N) time, O(N) space.
        Lookup: O(1) average time.
    """
    commit_map: Dict[str, Commit] = {}
    for commit in commits:
        commit_map[commit.commit_hash] = commit
        # Also map short hash for developer convenience
        commit_map[commit.short_hash] = commit
    return commit_map


def build_developer_map(
    commits: Sequence[Commit],
    file_changes: Optional[Sequence[Any]] = None,
) -> Dict[str, Developer]:
    """Aggregate developer statistics into an email -> Developer hash map.
    
    Complexity:
        Construction: O(N + M) time.
        Lookup: O(1) average time by normalized email.
    """
    dev_map: Dict[str, Developer] = {}

    for commit in commits:
        email = commit.author_email.lower().strip() or f"{commit.author.lower().strip()}@unknown"
        if email not in dev_map:
            dev_map[email] = Developer(name=commit.author, email=email)
        
        dev = dev_map[email]
        dev.add_commit(
            insertions=commit.insertions,
            deletions=commit.deletions,
            files=set(commit.files_changed),
        )

    return dev_map


def build_file_stats_map(commits: Sequence[Commit]) -> Dict[str, Dict[str, Any]]:
    """Aggregate file modification metrics into a file_path -> stats hash map.
    
    Complexity:
        Construction: O(N * F) where F is average files touched per commit.
        Lookup: O(1) average time by normalized path.
    """
    stats_map: Dict[str, Dict[str, Any]] = {}

    for commit in commits:
        for file_path in commit.files_changed:
            norm_path = file_path.replace("\\", "/")
            if norm_path not in stats_map:
                stats_map[norm_path] = {
                    "file_path": norm_path,
                    "modification_count": 0,
                    "insertions": 0,
                    "deletions": 0,
                    "total_changes": 0,
                    "authors": set(),
                    "latest_commit_date": commit.commit_date,
                    "first_commit_date": commit.commit_date,
                }
            
            entry = stats_map[norm_path]
            entry["modification_count"] += 1
            entry["authors"].add(commit.author_email or commit.author)
            if commit.commit_date > entry["latest_commit_date"]:
                entry["latest_commit_date"] = commit.commit_date
            if commit.commit_date < entry["first_commit_date"]:
                entry["first_commit_date"] = commit.commit_date

    return stats_map


def build_risk_map(risk_results: Sequence[RiskResult]) -> Dict[str, RiskResult]:
    """Index risk evaluation results by file path.
    
    Complexity:
        Construction: O(N) time.
        Lookup: O(1) average time.
    """
    return {r.file_path: r for r in risk_results}


# ============================================================================
# 2. HEAP / PRIORITY QUEUE (Top-K selection in O(N log K))
# ============================================================================

def get_top_risky_files(
    file_risks: Union[Dict[str, RiskResult], Sequence[RiskResult]],
    k: int = 5,
) -> List[RiskResult]:
    """Retrieve the top-K riskiest files using a min-heap priority queue.
    
    Rather than sorting the entire dataset of N files in O(N log N) time,
    heapq.nlargest maintains a heap of size K, evaluating elements in O(N log K) time
    and O(K) auxiliary memory.
    
    Args:
        file_risks: Collection or dictionary of RiskResult instances.
        k: Maximum number of risky files to extract.
        
    Returns:
        List of top-K RiskResult objects, ordered by highest risk score descending.
    """
    if k <= 0:
        return []
    
    items: Sequence[RiskResult] = (
        list(file_risks.values()) if isinstance(file_risks, dict) else list(file_risks)
    )
    if not items:
        return []

    # O(N log K) extraction using score as key
    return heapq.nlargest(k, items, key=lambda r: (r.score, len(r.reasons)))


def get_top_changed_files(
    file_stats: Union[Dict[str, Dict[str, Any]], Sequence[Dict[str, Any]]],
    k: int = 5,
) -> List[Dict[str, Any]]:
    """Retrieve top-K most frequently modified files using heapq.
    
    Time Complexity: O(N log K) where N = total files, K = requested subset.
    """
    if k <= 0:
        return []

    items = list(file_stats.values()) if isinstance(file_stats, dict) else list(file_stats)
    if not items:
        return []

    return heapq.nlargest(
        k,
        items,
        key=lambda entry: (
            entry.get("modification_count", 0),
            entry.get("total_changes", 0),
        ),
    )


# ============================================================================
# 3. BINARY SEARCH (Chronological date-range slicing in O(log N + M))
# ============================================================================

def find_commits_between(
    sorted_commits: Sequence[Commit],
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Commit]:
    """Extract commits in [start_date, end_date] using binary search (bisect).
    
    PREREQUISITE:
        sorted_commits MUST be sorted chronologically (oldest commit first).
        
    Complexity:
        Binary Search: O(log N) to find boundary indices.
        Slicing: O(M) where M is the number of commits in range.
        Total Time: O(log N + M) vs O(N) linear filter.
    """
    if not sorted_commits:
        return []

    # Key list of commit datetimes for bisect comparisons
    commit_dates = [c.commit_date for c in sorted_commits]

    # Find lower bound index
    if start_date is not None:
        start_idx = bisect.bisect_left(commit_dates, start_date)
    else:
        start_idx = 0

    # Find upper bound index (inclusive)
    if end_date is not None:
        end_idx = bisect.bisect_right(commit_dates, end_date)
    else:
        end_idx = len(sorted_commits)

    return list(sorted_commits[start_idx:end_idx])


# ============================================================================
# 4. STACK / LIFO (AnalysisHistoryStack for filter state undo)
# ============================================================================

class AnalysisHistoryStack(Generic[T]):
    """LIFO Stack managing analysis snapshots, filter states, and undo operations.
    
    Demonstrates true LIFO behavior for interactive and piped CLI workflows.
    """

    def __init__(self) -> None:
        self._items: List[T] = []

    def push(self, item: T) -> None:
        """Push a state snapshot onto the stack. Time: O(1)."""
        self._items.append(item)

    def pop(self) -> T:
        """Pop and return the top item. Time: O(1).
        
        Raises:
            AnalysisError: If stack is empty.
        """
        if self.is_empty():
            raise AnalysisError("Cannot pop from an empty AnalysisHistoryStack")
        return self._items.pop()

    def peek(self) -> Optional[T]:
        """Inspect the top item without removing it. Time: O(1)."""
        if self.is_empty():
            return None
        return self._items[-1]

    def is_empty(self) -> bool:
        """Check if stack has 0 elements. Time: O(1)."""
        return len(self._items) == 0

    def size(self) -> int:
        """Return total elements on the stack."""
        return len(self._items)

    def undo_last_filter(self) -> Optional[T]:
        """Roll back to the previous snapshot state.
        
        Returns:
            The prior active state, or None if no prior state exists.
        """
        if len(self._items) <= 1:
            return None
        # Discard current top state
        self._items.pop()
        # Return new top state
        return self._items[-1]

    def clear(self) -> None:
        """Reset the stack."""
        self._items.clear()

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"AnalysisHistoryStack(depth={len(self._items)})"
