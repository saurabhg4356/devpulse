"""Unit tests for Data Structures and Algorithms (DSA) utilities."""

from datetime import datetime, timezone, timedelta
import pytest

from models.commit import Commit
from models.exceptions import AnalysisError
from models.risk import RiskResult
from services.dsa_utils import (
    AnalysisHistoryStack,
    build_commit_map,
    build_developer_map,
    build_file_stats_map,
    build_risk_map,
    find_commits_between,
    get_top_changed_files,
    get_top_risky_files,
)


class TestHashMapIndexing:
    """Verify O(1) hash map construction and lookup operations."""

    def test_build_commit_map(self, sample_commits: list[Commit]) -> None:
        cmap = build_commit_map(sample_commits)
        assert len(cmap) >= len(sample_commits)
        first = sample_commits[0]
        # Direct O(1) lookup by full hash
        assert cmap[first.commit_hash] == first
        # Direct O(1) lookup by short hash
        assert cmap[first.short_hash] == first

    def test_build_developer_map(self, sample_commits: list[Commit]) -> None:
        dmap = build_developer_map(sample_commits)
        assert "alice@example.com" in dmap
        assert "bob@example.com" in dmap
        alice = dmap["alice@example.com"]
        assert alice.commit_count == 2
        assert alice.lines_added == 160

    def test_build_file_stats_map(self, sample_commits: list[Commit]) -> None:
        fmap = build_file_stats_map(sample_commits)
        assert "auth/service.py" in fmap
        auth_stats = fmap["auth/service.py"]
        assert auth_stats["modification_count"] == 2
        assert len(auth_stats["authors"]) >= 2

    def test_build_risk_map(self, sample_risk_results: list[RiskResult]) -> None:
        rmap = build_risk_map(sample_risk_results)
        assert "src/services/payment.py" in rmap
        assert rmap["src/services/payment.py"].score == 91.0


class TestHeapPriorityQueue:
    """Verify O(N log K) top-K extraction using heapq."""

    def test_get_top_risky_files(self, sample_risk_results: list[RiskResult]) -> None:
        top_2 = get_top_risky_files(sample_risk_results, k=2)
        assert len(top_2) == 2
        # Must be ordered by highest risk first
        assert top_2[0].score == 91.0
        assert top_2[1].score == 84.0

    def test_get_top_risky_files_edge_cases(self, sample_risk_results: list[RiskResult]) -> None:
        assert get_top_risky_files([], k=5) == []
        assert get_top_risky_files(sample_risk_results, k=0) == []
        top_all = get_top_risky_files(sample_risk_results, k=100)
        assert len(top_all) == len(sample_risk_results)
        assert top_all[0].score >= top_all[-1].score

    def test_get_top_changed_files(self, sample_commits: list[Commit]) -> None:
        fmap = build_file_stats_map(sample_commits)
        top_files = get_top_changed_files(fmap, k=2)
        assert len(top_files) <= 2
        assert top_files[0]["modification_count"] >= top_files[-1]["modification_count"]


class TestBinarySearch:
    """Verify O(log N) chronological date-range queries via bisect."""

    def test_find_commits_between_date_range(self, sample_commits: list[Commit]) -> None:
        # sample_commits dates: Day 0, Day 7, Day 14, Day 21, Day 28
        base = sample_commits[0].commit_date
        start = base + timedelta(days=5)
        end = base + timedelta(days=22)

        matched = find_commits_between(sample_commits, start_date=start, end_date=end)
        # Should include Day 7, Day 14, Day 21 (3 commits)
        assert len(matched) == 3
        assert matched[0].commit_date >= start
        assert matched[-1].commit_date <= end

    def test_find_commits_between_open_bounds(self, sample_commits: list[Commit]) -> None:
        all_commits = find_commits_between(sample_commits, None, None)
        assert len(all_commits) == len(sample_commits)

        none_match = find_commits_between(
            sample_commits,
            start_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        assert len(none_match) == 0


class TestLIFOStack:
    """Verify AnalysisHistoryStack LIFO operations and undo functionality."""

    def test_stack_push_pop_peek(self) -> None:
        stack: AnalysisHistoryStack[str] = AnalysisHistoryStack()
        assert stack.is_empty()
        assert stack.peek() is None

        stack.push("state_1")
        stack.push("state_2")
        assert not stack.is_empty()
        assert stack.size() == 2
        assert stack.peek() == "state_2"

        popped = stack.pop()
        assert popped == "state_2"
        assert stack.peek() == "state_1"

    def test_stack_pop_empty_raises(self) -> None:
        stack: AnalysisHistoryStack[int] = AnalysisHistoryStack()
        with pytest.raises(AnalysisError):
            stack.pop()

    def test_stack_undo_last_filter(self) -> None:
        stack: AnalysisHistoryStack[dict] = AnalysisHistoryStack()
        stack.push({"filter": "all"})
        stack.push({"filter": "last_30_days"})
        stack.push({"filter": "last_7_days"})

        # Undo to last_30_days
        previous = stack.undo_last_filter()
        assert previous == {"filter": "last_30_days"}
        assert stack.peek() == {"filter": "last_30_days"}
        assert stack.size() == 2

        # Undo to all
        base = stack.undo_last_filter()
        assert base == {"filter": "all"}
        assert stack.size() == 1

        # Cannot undo base
        assert stack.undo_last_filter() is None
