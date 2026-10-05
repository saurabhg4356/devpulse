"""Terminal and textual formatting utilities for DevPulse."""

from typing import List, Tuple, Union


def format_number(val: Union[int, float]) -> str:
    """Format numeric values with comma separators."""
    if isinstance(val, float):
        return f"{val:,.2f}"
    return f"{val:,}"


def format_lines_diff(insertions: int, deletions: int) -> str:
    """Format insertions and deletions into standard diff string (+10 / -5)."""
    return f"+{insertions:,} / -{deletions:,}"


def format_section_header(title: str, width: int = 60) -> str:
    """Generate a clean ASCII section header."""
    border = "=" * width
    return f"\n{border}\n{title.upper().center(width)}\n{border}\n"


def format_risk_badge(level: str, score: float) -> str:
    """Format risk level with score."""
    return f"[{level}] ({score:.1f}/100)"


from typing import Union
