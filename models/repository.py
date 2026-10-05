"""Repository model representing high-level repository metadata and health indicators."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from utils.dates import days_between, format_display_date, format_iso_datetime
from utils.validators import validate_non_negative_int, validate_repository_path


class Repository:
    """Encapsulates metadata and high-level health metrics of an analyzed Git repository.
    
    Provides summary methods, activity level calculations, and chronological age.
    """

    def __init__(
        self,
        repository_path: Path,
        repository_name: Optional[str] = None,
        current_branch: str = "main",
        total_commits: int = 0,
        total_files: int = 0,
        active_developers: int = 0,
        first_commit_date: Optional[datetime] = None,
        latest_commit_date: Optional[datetime] = None,
        health_score: float = 100.0,
    ) -> None:
        self._path = validate_repository_path(repository_path)
        self._name = repository_name or self._path.name
        self._current_branch = current_branch or "unknown"
        self._total_commits = validate_non_negative_int(total_commits, "total_commits")
        self._total_files = validate_non_negative_int(total_files, "total_files")
        self._active_developers = validate_non_negative_int(active_developers, "active_developers")
        self._first_commit_date = first_commit_date
        self._latest_commit_date = latest_commit_date
        self._health_score = max(0.0, min(100.0, float(health_score)))

    @property
    def path(self) -> Path:
        return self._path

    @property
    def name(self) -> str:
        return self._name

    @property
    def current_branch(self) -> str:
        return self._current_branch

    @current_branch.setter
    def current_branch(self, branch: str) -> None:
        self._current_branch = branch.strip() if branch else "unknown"

    @property
    def total_commits(self) -> int:
        return self._total_commits

    @total_commits.setter
    def total_commits(self, count: int) -> None:
        self._total_commits = validate_non_negative_int(count, "total_commits")

    @property
    def total_files(self) -> int:
        return self._total_files

    @total_files.setter
    def total_files(self, count: int) -> None:
        self._total_files = validate_non_negative_int(count, "total_files")

    @property
    def active_developers(self) -> int:
        return self._active_developers

    @active_developers.setter
    def active_developers(self, count: int) -> None:
        self._active_developers = validate_non_negative_int(count, "active_developers")

    @property
    def first_commit_date(self) -> Optional[datetime]:
        return self._first_commit_date

    @first_commit_date.setter
    def first_commit_date(self, dt: Optional[datetime]) -> None:
        self._first_commit_date = dt

    @property
    def latest_commit_date(self) -> Optional[datetime]:
        return self._latest_commit_date

    @latest_commit_date.setter
    def latest_commit_date(self, dt: Optional[datetime]) -> None:
        self._latest_commit_date = dt

    @property
    def health_score(self) -> float:
        return self._health_score

    @health_score.setter
    def health_score(self, score: float) -> None:
        self._health_score = max(0.0, min(100.0, float(score)))

    def age_in_days(self) -> int:
        """Calculate repository history span in calendar days."""
        if not self._first_commit_date or not self._latest_commit_date:
            return 0
        return days_between(self._first_commit_date, self._latest_commit_date)

    def days_since_last_commit(self) -> int:
        """Number of days between latest commit and present day."""
        if not self._latest_commit_date:
            return 0
        now = datetime.now(timezone.utc)
        return days_between(self._latest_commit_date, now)

    def activity_level(self) -> str:
        """Derive activity classification based on recency and commit density."""
        if self._total_commits == 0 or not self._latest_commit_date:
            return "DORMANT"
        days_idle = self.days_since_last_commit()
        if days_idle > 180:
            return "DORMANT"
        if days_idle > 60:
            return "LOW"
        if self._total_commits >= 20 and days_idle <= 14:
            return "HIGH"
        return "MODERATE"

    def summary(self) -> Dict[str, Any]:
        """Generate structured dictionary summary of repository state."""
        return {
            "repository_name": self._name,
            "repository_path": str(self._path),
            "current_branch": self._current_branch,
            "total_commits": self._total_commits,
            "total_files": self._total_files,
            "active_developers": self._active_developers,
            "first_commit": format_display_date(self._first_commit_date),
            "latest_commit": format_display_date(self._latest_commit_date),
            "age_days": self.age_in_days(),
            "activity_level": self.activity_level(),
            "health_score": round(self._health_score, 1),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize repository metadata for export."""
        return {
            "name": self._name,
            "path": str(self._path),
            "branch": self._current_branch,
            "total_commits": self._total_commits,
            "total_files": self._total_files,
            "active_developers": self._active_developers,
            "first_commit_date": format_iso_datetime(self._first_commit_date),
            "latest_commit_date": format_iso_datetime(self._latest_commit_date),
            "health_score": self._health_score,
            "activity_level": self.activity_level(),
        }

    def __repr__(self) -> str:
        return (
            f"Repository(name={self._name!r}, branch={self._current_branch!r}, "
            f"commits={self._total_commits}, files={self._total_files})"
        )
