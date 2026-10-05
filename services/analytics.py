"""Analytics engine for DevPulse using pandas and NumPy.

Calculates code churn statistics, file volatility heuristics, developer contributions,
and high-level repository health scores.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
import numpy as np
import pandas as pd

from models.commit import Commit
from models.risk import RiskResult
from utils.dates import days_between


def compute_churn_metrics(commits: Sequence[Commit]) -> Dict[str, Any]:
    """Calculate aggregate code churn metrics using pandas and NumPy.
    
    Returns:
        Dictionary containing total additions, deletions, churn, mean/median commit size,
        largest commit, and temporal distribution (active days and months).
    """
    if not commits:
        return {
            "total_commits": 0,
            "total_additions": 0,
            "total_deletions": 0,
            "total_churn": 0,
            "mean_commit_size": 0.0,
            "median_commit_size": 0.0,
            "largest_commit": None,
            "active_days": {},
            "active_months": {},
        }

    records = [
        {
            "hash": c.short_hash,
            "author": c.author,
            "date": c.commit_date,
            "insertions": c.insertions,
            "deletions": c.deletions,
            "churn": c.total_changes,
            "files_count": c.file_count,
        }
        for c in commits
    ]
    df = pd.DataFrame(records)

    total_additions = int(df["insertions"].sum())
    total_deletions = int(df["deletions"].sum())
    total_churn = int(df["churn"].sum())
    mean_size = round(float(df["churn"].mean()), 2)
    median_size = round(float(np.median(df["churn"])), 2)

    # Find largest commit
    max_idx = df["churn"].idxmax()
    largest_record = df.loc[max_idx].to_dict()
    largest_record["date"] = largest_record["date"].isoformat()

    # Temporal distributions: day of week and month
    df["day_name"] = df["date"].dt.day_name()
    df["month_year"] = df["date"].dt.tz_localize(None).dt.to_period("M").astype(str)

    active_days = df["day_name"].value_counts().to_dict()
    active_months = df["month_year"].value_counts().sort_index().to_dict()

    return {
        "total_commits": len(commits),
        "total_additions": total_additions,
        "total_deletions": total_deletions,
        "total_churn": total_churn,
        "mean_commit_size": mean_size,
        "median_commit_size": median_size,
        "largest_commit": largest_record,
        "active_days": active_days,
        "active_months": active_months,
    }


def compute_file_volatility(
    file_stat: Dict[str, Any],
    total_commits: int,
    now: Optional[datetime] = None,
) -> float:
    """Calculate an engineering heuristic volatility score (0-100) for a file.
    
    Factors:
    - Relative modification frequency (how often touched vs total commits)
    - Normalized code churn volume
    - Multiple author churn / ownership dispersion
    - Recency of modifications
    
    Disclaimer: This is an empirical engineering heuristic to highlight code hotspots,
    not a scientifically proven defect predictor.
    """
    if total_commits <= 0:
        return 0.0

    mods = file_stat.get("modification_count", 1)
    churn = file_stat.get("total_changes", 0)
    authors_count = len(file_stat.get("authors", []))
    latest_date = file_stat.get("latest_commit_date")

    # Frequency factor (0 - 40 points)
    freq_ratio = min(1.0, mods / max(1, total_commits))
    freq_score = freq_ratio * 40.0

    # Churn factor (0 - 30 points, logarithmic scaling)
    churn_score = min(30.0, np.log1p(churn) * 4.5)

    # Multi-contributor factor (0 - 20 points)
    author_score = min(20.0, max(0, authors_count - 1) * 6.5)

    # Recency factor (0 - 10 points)
    recency_score = 5.0
    if latest_date:
        ref_now = now or datetime.now(timezone.utc)
        days_ago = days_between(latest_date, ref_now)
        if days_ago <= 14:
            recency_score = 10.0
        elif days_ago <= 60:
            recency_score = 6.0
        elif days_ago <= 180:
            recency_score = 3.0
        else:
            recency_score = 1.0

    raw_volatility = freq_score + churn_score + author_score + recency_score
    return round(float(np.clip(raw_volatility, 0.0, 100.0)), 2)


def calculate_repository_health_score(
    commits: Sequence[Commit],
    anomalies_count: int = 0,
    high_risk_files_count: int = 0,
    total_files: int = 1,
) -> Tuple[float, str]:
    """Calculate an explainable repository health score (0-100).
    
    Starts at a baseline of 100 and applies risk and instability deductions:
    - High-risk file density penalty
    - Anomaly concentration penalty
    - High commit churn variance penalty
    
    Returns:
        Tuple of (health_score: float, release_risk_category: str)
    """
    if not commits:
        return 100.0, "LOW"

    score = 100.0

    # 1. High risk file proportion penalty (up to 35 points)
    if total_files > 0:
        risk_file_ratio = min(1.0, high_risk_files_count / total_files)
        score -= (risk_file_ratio * 35.0)

    # 2. Anomaly density penalty (up to 25 points)
    anomaly_ratio = min(1.0, anomalies_count / max(1, len(commits)))
    score -= (anomaly_ratio * 50.0)

    # 3. Variance in commit sizes penalty (up to 15 points)
    churn_list = [c.total_changes for c in commits]
    if len(churn_list) > 3:
        std_dev = float(np.std(churn_list))
        mean_churn = float(np.mean(churn_list))
        cv = std_dev / (mean_churn + 1e-6)  # coefficient of variation
        if cv > 2.5:
            score -= 15.0
        elif cv > 1.5:
            score -= 8.0

    final_score = round(float(np.clip(score, 10.0, 100.0)), 1)

    # Derive release risk category
    if final_score >= 80.0:
        release_risk = "LOW"
    elif final_score >= 60.0:
        release_risk = "MEDIUM"
    elif final_score >= 40.0:
        release_risk = "HIGH"
    else:
        release_risk = "CRITICAL"

    return final_score, release_risk
