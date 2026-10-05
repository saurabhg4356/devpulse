"""Unit tests for StorageService CSV persistence."""

from pathlib import Path
import pytest

from models.commit import Commit
from models.developer import Developer
from models.exceptions import StorageError
from models.risk import RiskResult
from services.dsa_utils import build_file_stats_map
from services.storage import StorageService


class TestStorageService:
    """Verify validated CSV persistence and roundtrip reloading."""

    def test_save_and_load_roundtrip(
        self,
        tmp_path: Path,
        sample_commits: list[Commit],
        sample_developers: list[Developer],
        sample_risk_results: list[RiskResult],
    ) -> None:
        storage = StorageService(base_dir=tmp_path)
        file_stats = build_file_stats_map(sample_commits)

        # Save
        saved_paths = storage.save_analysis(
            output_dir=tmp_path,
            commits=sample_commits,
            file_stats=file_stats,
            developers=sample_developers,
            risks=sample_risk_results,
        )
        assert len(saved_paths) == 4
        assert (tmp_path / "commits.csv").exists()
        assert (tmp_path / "files.csv").exists()
        assert (tmp_path / "developers.csv").exists()
        assert (tmp_path / "risks.csv").exists()

        # Load
        loaded = storage.load_analysis(tmp_path)
        assert len(loaded["commits"]) == len(sample_commits)
        assert len(loaded["developers"]) == len(sample_developers)
        assert len(loaded["risks"]) == len(sample_risk_results)
        assert loaded["commits"][0].commit_hash == sample_commits[0].commit_hash

    def test_load_nonexistent_dir_raises(self, tmp_path: Path) -> None:
        storage = StorageService()
        with pytest.raises(StorageError):
            storage.load_analysis(tmp_path / "does_not_exist")

    def test_load_malformed_csv_raises(self, tmp_path: Path) -> None:
        storage = StorageService()
        bad_csv = tmp_path / "commits.csv"
        bad_csv.write_text("random_col1,random_col2\nval1,val2\n", encoding="utf-8")
        with pytest.raises(StorageError):
            storage.load_analysis(tmp_path)
