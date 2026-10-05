"""Developer model representing commit and change contribution metrics.

This model is designed strictly for repository activity distribution analysis
(e.g., detecting single points of failure, code ownership dispersion, and work patterns)
and NOT for individual performance evaluation or surveillance.
"""

from typing import Any, Dict, Optional, Set
from utils.validators import is_valid_email, validate_non_negative_int


class Developer:
    """Encapsulates aggregate repository contribution metrics for a contributor.
    
    Attributes:
        name: Contributor display name.
        email: Canonical contributor email address.
        commit_count: Total commits authored.
        lines_added: Gross insertions across commits.
        lines_deleted: Gross deletions across commits.
    """

    def __init__(
        self,
        name: str,
        email: str,
        commit_count: int = 0,
        lines_added: int = 0,
        lines_deleted: int = 0,
        files_changed: Optional[Set[str]] = None,
    ) -> None:
        self._name = name.strip() if name else "Unknown"
        self._email = email.strip().lower() if email else "unknown@domain.local"
        self._commit_count = validate_non_negative_int(commit_count, "commit_count")
        self._lines_added = validate_non_negative_int(lines_added, "lines_added")
        self._lines_deleted = validate_non_negative_int(lines_deleted, "lines_deleted")
        self._files_changed: Set[str] = set(files_changed) if files_changed else set()

    @property
    def name(self) -> str:
        return self._name

    @property
    def email(self) -> str:
        return self._email

    @property
    def commit_count(self) -> int:
        return self._commit_count

    @property
    def lines_added(self) -> int:
        return self._lines_added

    @property
    def lines_deleted(self) -> int:
        return self._lines_deleted

    @property
    def total_changes(self) -> int:
        """Total churn (insertions + deletions) authored."""
        return self._lines_added + self._lines_deleted

    @property
    def unique_files_count(self) -> int:
        """Number of unique files touched by this developer."""
        return len(self._files_changed)

    @property
    def files_changed(self) -> Set[str]:
        """Set of unique file paths modified by this developer."""
        return set(self._files_changed)

    @property
    def average_commit_size(self) -> float:
        """Mean lines changed per commit."""
        if self._commit_count == 0:
            return 0.0
        return round(self.total_changes / self._commit_count, 2)

    @property
    def activity_score(self) -> float:
        """Normalized activity weight based on commit volume and code churn."""
        # Log-like or weighted blend of commit count and churn
        score = (self._commit_count * 5.0) + (self.total_changes * 0.01)
        return round(score, 2)

    def add_commit(self, insertions: int, deletions: int, files: Optional[Set[str]] = None) -> None:
        """Record an additional commit for this contributor."""
        self._commit_count += 1
        self._lines_added += max(0, int(insertions))
        self._lines_deleted += max(0, int(deletions))
        if files:
            self._files_changed.update(files)

    def summary(self) -> str:
        """Formatted summary of repository activity."""
        return (
            f"{self._name} <{self._email}>: {self._commit_count} commits, "
            f"+{self._lines_added:,}/-{self._lines_deleted:,} lines, "
            f"{self.unique_files_count} files touched"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert developer metrics to dictionary for serialization."""
        return {
            "name": self._name,
            "email": self._email,
            "commit_count": self._commit_count,
            "lines_added": self._lines_added,
            "lines_deleted": self._lines_deleted,
            "total_changes": self.total_changes,
            "unique_files_count": self.unique_files_count,
            "average_commit_size": self.average_commit_size,
            "activity_score": self.activity_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Developer":
        """Instantiate Developer from dictionary."""
        return cls(
            name=data["name"],
            email=data["email"],
            commit_count=data.get("commit_count", 0),
            lines_added=data.get("lines_added", 0),
            lines_deleted=data.get("lines_deleted", 0),
        )

    def __repr__(self) -> str:
        return (
            f"Developer(name={self._name!r}, email={self._email!r}, "
            f"commits={self._commit_count}, churn={self.total_changes})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Developer):
            return False
        return self._email == other._email
