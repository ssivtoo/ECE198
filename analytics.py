"""
Delirium risk-scoring engine.

Clinical basis:
  - Excessive noise  → disrupts sleep, primary ICU delirium driver
  - Excessive light  → disrupts circadian rhythm
  - Dehydration      → cognitive impairment accelerant

Score: 0-100, higher = greater delirium risk.
Thresholds: LOW < 30 <= MODERATE < 60 <= HIGH
"""

from __future__ import annotations


def compute_risk_score(
    light_red: bool,
    noise_red: bool,
    hydr_red: bool,
    is_empty: bool,
    drink_rate_slow: bool,
) -> int:
    """Return composite delirium risk score 0-100."""
    score = 0
    if noise_red:
        score += 40  # strongest sleep disruptor
    if light_red:
        score += 25  # circadian disruption
    if is_empty:
        score += 35  # critical dehydration
    elif drink_rate_slow:
        score += 20  # inadequate intake rate
    elif hydr_red:
        score += 15  # general low hydration
    return min(100, score)


def risk_level(score: int) -> tuple[str, str]:
    """Return (label, hex_color) for a given score."""
    if score >= 60:
        return "HIGH", "#e53e3e"
    if score >= 30:
        return "MODERATE", "#dd6b20"
    return "LOW", "#38a169"


def trend(values: list[float]) -> str:
    """
    Linear-regression slope over values.
    Returns 'rising', 'falling', or 'stable'.
    Requires at least 4 data points.
    """
    n = len(values)
    if n < 4:
        return "stable"
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(values) / n
    numerator = sum((xs[i] - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return "stable"
    slope = numerator / denominator
    if slope > 0.5:
        return "rising"
    if slope < -0.5:
        return "falling"
    return "stable"
