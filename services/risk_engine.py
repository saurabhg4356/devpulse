"""RiskEngine service evaluating codebase and release risks using transparent heuristics.

Computes file-level risk scores (0-100) and structured RiskResult models with explainable
reasons and pragmatic recommendations. Configurable thresholds and factor weights.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np

from config.settings import DEFAULT_CONFIG, DevPulseConfig
from models.commit import Commit
from models.risk import ReleaseRisk, RiskResult
from services.dsa_utils import build_file_stats_map, get_top_risky_files
from utils.dates import days_between


class RiskEngine:
    """Calculates multidimensional codebase and release risk evaluations.
    
    Disclaimer: DevPulse risk scores are empirical software engineering heuristics
    designed to direct review focus and testing priorities. They do not claim
    the definitive presence of defects or software bugs.
    """

    def __init__(self, config: Optional[DevPulseConfig] = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.thresholds = self.config.risk_thresholds
        self.weights = self.config.risk_weights

    def evaluate_file(
        self,
        file_path: str,
        stats: Dict[str, Any],
        total_repo_commits: int,
        mean_repo_churn: float = 100.0,
        now: Optional[datetime] = None,
    ) -> RiskResult:
        """Evaluate risk score (0-100) and generate human-readable reasons for a single file.
        
        Args:
            file_path: Path of file under evaluation.
            stats: File statistics dict from build_file_stats_map.
            total_repo_commits: Total commits analyzed in the repository.
            mean_repo_churn: Average churn per commit across repository.
            now: Current reference datetime for recency scoring.
            
        Returns:
            RiskResult with numeric score, categorical level, reasons, and actions.
        """
        reasons: List[str] = []
        factors: Dict[str, float] = {}

        mods = stats.get("modification_count", 1)
        churn = stats.get("total_changes", 0)
        authors = stats.get("authors", set())
        author_count = len(authors)
        latest_date = stats.get("latest_commit_date")

        # 1. Modification Frequency Factor (0 - 100)
        # Ratio of commits touching this file relative to total repository commits
        freq_ratio = mods / max(1, total_repo_commits)
        freq_factor = float(np.clip(freq_ratio * 250.0, 0.0, 100.0))
        factors["frequency"] = freq_factor
        if freq_factor >= 50.0:
            reasons.append("High modification frequency relative to repository activity")

        # 2. Code Churn Volume Factor (0 - 100)
        # Scaled against repository mean churn
        churn_ratio = churn / max(1.0, mean_repo_churn * 3.0)
        churn_factor = float(np.clip(churn_ratio * 40.0, 0.0, 100.0))
        factors["churn"] = churn_factor
        if churn >= 500 or churn_factor >= 55.0:
            reasons.append(f"Large accumulated code churn ({churn:,} lines changed)")

        # 3. Contributor Ownership Dispersion Factor (0 - 100)
        # Higher score when many different developers modify the same file (coordination overhead)
        if author_count > 3:
            author_factor = min(100.0, 40.0 + (author_count * 12.0))
            reasons.append(f"Multiple developers ({author_count}) actively modified this file")
        elif author_count == 1:
            # Low coordination risk, but possible knowledge silo
            author_factor = 15.0
        else:
            author_factor = 30.0
        factors["contributors"] = author_factor

        # 4. Recency & Activity Spike Factor (0 - 100)
        ref_now = now or datetime.now(timezone.utc)
        days_ago = days_between(latest_date, ref_now) if latest_date else 999
        if days_ago <= 7:
            recency_factor = 90.0
            reasons.append("Recent modifications within the past 7 days")
        elif days_ago <= 30:
            recency_factor = 60.0
        elif days_ago <= 90:
            recency_factor = 30.0
        else:
            recency_factor = 10.0
        factors["recency"] = recency_factor

        # 5. Volatility Weighting
        volatility = stats.get("volatility_score", 0.0)
        if volatility >= 65.0:
            reasons.append("High historical volatility score across multiple releases")

        # Weighted aggregate score
        raw_score = (
            freq_factor * self.weights.frequency_weight
            + churn_factor * self.weights.churn_weight
            + author_factor * self.weights.contributor_weight
            + recency_factor * self.weights.recency_weight
            + min(100.0, volatility) * self.weights.large_commit_weight
        )
        final_score = round(float(np.clip(raw_score, 0.0, 100.0)), 1)
        level = self.thresholds.categorize(final_score)

        if not reasons:
            reasons.append("Standard modification volume and historical stability")

        # Recommended Action based on level
        if level == "CRITICAL":
            action = "Immediate peer review required; execute targeted unit and integration regression suites."
        elif level == "HIGH":
            action = "Review recent changes carefully and run related regression tests before release."
        elif level == "MEDIUM":
            action = "Standard code review and sanity checks recommended."
        else:
            action = "Low risk; standard continuous integration pass is sufficient."

        return RiskResult(
            file_path=file_path,
            score=final_score,
            level=level,
            reasons=reasons,
            recommended_action=action,
            factors=factors,
        )

    def evaluate_repository(
        self,
        commits: Sequence[Commit],
        file_stats: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, RiskResult], ReleaseRisk]:
        """Evaluate all repository files and calculate total release risk.
        
        Args:
            commits: List of commits analyzed.
            file_stats: Optional precomputed file stats map.
            
        Returns:
            Tuple of (file_risks_dict, ReleaseRisk)
        """
        stats_map = file_stats or build_file_stats_map(commits)
        total_commits = len(commits)
        mean_churn = (
            float(np.mean([c.total_changes for c in commits])) if commits else 50.0
        )

        file_risks: Dict[str, RiskResult] = {}
        for path, stats in stats_map.items():
            result = self.evaluate_file(
                file_path=path,
                stats=stats,
                total_repo_commits=total_commits,
                mean_repo_churn=mean_churn,
            )
            file_risks[path] = result

        # Compute overall release risk
        if not file_risks:
            release_risk = ReleaseRisk(
                overall_score=0.0,
                level="LOW",
                top_risk_drivers=[],
                summary_text="No modified files detected in current scope.",
            )
            return file_risks, release_risk

        # Top risky files via Heap Priority Queue
        top_risky = get_top_risky_files(file_risks, k=5)
        top_scores = [r.score for r in top_risky]
        
        # Release risk is heavily influenced by the top 5 hotspots
        overall_score = float(np.mean(top_scores)) if top_scores else 0.0
        overall_level = self.thresholds.categorize(overall_score)

        drivers = [f"{r.file_path} ({r.score:.0f})" for r in top_risky if r.score >= 50.0]
        if not drivers:
            drivers = [f"{top_risky[0].file_path} ({top_risky[0].score:.0f})"] if top_risky else []

        summary_text = (
            f"Release risk is {overall_level} ({overall_score:.1f}/100) driven by "
            f"{len(drivers)} elevated hotspot file(s)."
        )

        release_risk = ReleaseRisk(
            overall_score=overall_score,
            level=overall_level,
            top_risk_drivers=drivers,
            summary_text=summary_text,
        )

        return file_risks, release_risk
