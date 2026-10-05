"""StorageService for persisting and reloading DevPulse analysis datasets in CSV.

Guarantees data integrity, column validation, defensive parsing, and never mutates
the target Git repository. Raises StorageError on I/O or malformed schema errors.
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from models.commit import Commit
from models.developer import Developer
from models.exceptions import StorageError
from models.risk import RiskResult


# Mandatory CSV headers for schema validation
COMMIT_CSV_HEADERS = [
    "commit_hash", "short_hash", "author", "author_email", "commit_date",
    "message", "files_changed", "insertions", "deletions", "total_changes",
    "classification", "risk_score"
]

FILE_CSV_HEADERS = [
    "file_path", "modification_count", "total_changes", "volatility_score"
]

DEVELOPER_CSV_HEADERS = [
    "name", "email", "commit_count", "lines_added", "lines_deleted",
    "total_changes", "average_commit_size", "activity_score"
]

RISK_CSV_HEADERS = [
    "file_path", "score", "level", "reasons", "recommended_action"
]


class StorageService:
    """Manages CSV persistence for DevPulse analysis artifacts."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path("reports")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_analysis(
        self,
        output_dir: Path,
        commits: Sequence[Commit],
        file_stats: Dict[str, Dict[str, Any]],
        developers: Sequence[Developer],
        risks: Sequence[RiskResult],
    ) -> Dict[str, Path]:
        """Persist all analysis datasets into separate CSV files.
        
        Args:
            output_dir: Directory where CSV files should be written.
            commits: List of Commit objects.
            file_stats: Dictionary of file modification metrics.
            developers: List of Developer objects.
            risks: List of RiskResult objects.
            
        Returns:
            Dictionary mapping table name to written Path.
            
        Raises:
            StorageError: If disk write fails.
        """
        output_dir = Path(output_dir)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            saved_paths: Dict[str, Path] = {}

            # 1. commits.csv
            commits_path = output_dir / "commits.csv"
            with open(commits_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COMMIT_CSV_HEADERS)
                writer.writeheader()
                for c in commits:
                    row = c.to_dict()
                    row["files_changed"] = ";".join(row.get("files_changed", []))
                    writer.writerow({k: row.get(k, "") for k in COMMIT_CSV_HEADERS})
            saved_paths["commits"] = commits_path

            # 2. files.csv
            files_path = output_dir / "files.csv"
            with open(files_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FILE_CSV_HEADERS)
                writer.writeheader()
                for path, stat in file_stats.items():
                    writer.writerow({
                        "file_path": path,
                        "modification_count": stat.get("modification_count", 0),
                        "total_changes": stat.get("total_changes", 0),
                        "volatility_score": stat.get("volatility_score", 0.0),
                    })
            saved_paths["files"] = files_path

            # 3. developers.csv
            devs_path = output_dir / "developers.csv"
            with open(devs_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=DEVELOPER_CSV_HEADERS)
                writer.writeheader()
                for d in developers:
                    writer.writerow({k: d.to_dict().get(k, "") for k in DEVELOPER_CSV_HEADERS})
            saved_paths["developers"] = devs_path

            # 4. risks.csv
            risks_path = output_dir / "risks.csv"
            with open(risks_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=RISK_CSV_HEADERS)
                writer.writeheader()
                for r in risks:
                    row = r.to_dict()
                    writer.writerow({k: row.get(k, "") for k in RISK_CSV_HEADERS})
            saved_paths["risks"] = risks_path

            return saved_paths

        except Exception as err:
            raise StorageError(f"Failed to persist analysis to {output_dir}: {err}") from err

    def load_analysis(self, input_dir: Path) -> Dict[str, Any]:
        """Load and validate persisted CSV analysis files from a directory.
        
        Args:
            input_dir: Directory containing exported CSV files.
            
        Returns:
            Dictionary containing loaded domain models.
            
        Raises:
            StorageError: If required files are missing or columns are malformed.
        """
        input_dir = Path(input_dir)
        if not input_dir.exists() or not input_dir.is_dir():
            raise StorageError(f"Analysis storage directory not found: {input_dir}")

        result: Dict[str, Any] = {}

        # 1. Load commits
        commits_path = input_dir / "commits.csv"
        if commits_path.exists():
            result["commits"] = self._load_commits(commits_path)

        # 2. Load files
        files_path = input_dir / "files.csv"
        if files_path.exists():
            result["files"] = self._load_files(files_path)

        # 3. Load developers
        devs_path = input_dir / "developers.csv"
        if devs_path.exists():
            result["developers"] = self._load_developers(devs_path)

        # 4. Load risks
        risks_path = input_dir / "risks.csv"
        if risks_path.exists():
            result["risks"] = self._load_risks(risks_path)

        return result

    def _load_commits(self, path: Path) -> List[Commit]:
        try:
            commits: List[Commit] = []
            with open(path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not set(COMMIT_CSV_HEADERS).issubset(reader.fieldnames):
                    raise StorageError(f"Malformed headers in {path.name}")
                for row in reader:
                    commits.append(Commit.from_dict(row))
            return commits
        except Exception as err:
            if isinstance(err, StorageError):
                raise
            raise StorageError(f"Error reading {path.name}: {err}") from err

    def _load_files(self, path: Path) -> Dict[str, Dict[str, Any]]:
        try:
            files: Dict[str, Dict[str, Any]] = {}
            with open(path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not set(FILE_CSV_HEADERS).issubset(reader.fieldnames):
                    raise StorageError(f"Malformed headers in {path.name}")
                for row in reader:
                    fpath = row["file_path"]
                    files[fpath] = {
                        "file_path": fpath,
                        "modification_count": int(row.get("modification_count", 0)),
                        "total_changes": int(row.get("total_changes", 0)),
                        "volatility_score": float(row.get("volatility_score", 0.0)),
                    }
            return files
        except Exception as err:
            if isinstance(err, StorageError):
                raise
            raise StorageError(f"Error reading {path.name}: {err}") from err

    def _load_developers(self, path: Path) -> List[Developer]:
        try:
            developers: List[Developer] = []
            with open(path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not set(DEVELOPER_CSV_HEADERS).issubset(reader.fieldnames):
                    raise StorageError(f"Malformed headers in {path.name}")
                for row in reader:
                    developers.append(Developer.from_dict(row))
            return developers
        except Exception as err:
            if isinstance(err, StorageError):
                raise
            raise StorageError(f"Error reading {path.name}: {err}") from err

    def _load_risks(self, path: Path) -> List[RiskResult]:
        try:
            risks: List[RiskResult] = []
            with open(path, mode="r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not set(RISK_CSV_HEADERS).issubset(reader.fieldnames):
                    raise StorageError(f"Malformed headers in {path.name}")
                for row in reader:
                    risks.append(RiskResult.from_dict(row))
            return risks
        except Exception as err:
            if isinstance(err, StorageError):
                raise
            raise StorageError(f"Error reading {path.name}: {err}") from err
