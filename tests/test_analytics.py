"""
Unit tests for analytics.py — risk scoring, level classification, and trend detection.
Run with: pytest tests/
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import analytics


# ──────────────────────────────────────────────────────────────────────────────
# compute_risk_score
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeRiskScore:
    def test_no_alerts_returns_zero(self):
        assert analytics.compute_risk_score(False, False, False, False, False) == 0

    def test_noise_alone(self):
        assert analytics.compute_risk_score(False, True, False, False, False) == 40

    def test_light_alone(self):
        assert analytics.compute_risk_score(True, False, False, False, False) == 25

    def test_empty_bottle_alone(self):
        assert analytics.compute_risk_score(False, False, True, True, False) == 35

    def test_slow_drinking_alone(self):
        assert analytics.compute_risk_score(False, False, True, False, True) == 20

    def test_generic_low_hydration_alone(self):
        assert analytics.compute_risk_score(False, False, True, False, False) == 15

    def test_noise_plus_light(self):
        assert analytics.compute_risk_score(True, True, False, False, False) == 65

    def test_noise_plus_empty(self):
        assert analytics.compute_risk_score(False, True, True, True, False) == 75

    def test_all_alerts_capped_at_100(self):
        score = analytics.compute_risk_score(True, True, True, True, True)
        assert score <= 100

    def test_all_alerts_yields_high(self):
        score = analytics.compute_risk_score(True, True, True, True, False)
        assert score >= 60

    def test_empty_bottle_takes_priority_over_slow_drinking(self):
        score_empty = analytics.compute_risk_score(False, False, True, True, False)
        score_slow = analytics.compute_risk_score(False, False, True, False, True)
        assert score_empty > score_slow


# ──────────────────────────────────────────────────────────────────────────────
# risk_level
# ──────────────────────────────────────────────────────────────────────────────

class TestRiskLevel:
    def test_score_zero_is_low(self):
        label, color = analytics.risk_level(0)
        assert label == "LOW"
        assert color == "#38a169"

    def test_score_29_is_low(self):
        label, _ = analytics.risk_level(29)
        assert label == "LOW"

    def test_score_30_is_moderate(self):
        label, color = analytics.risk_level(30)
        assert label == "MODERATE"
        assert color == "#dd6b20"

    def test_score_59_is_moderate(self):
        label, _ = analytics.risk_level(59)
        assert label == "MODERATE"

    def test_score_60_is_high(self):
        label, color = analytics.risk_level(60)
        assert label == "HIGH"
        assert color == "#e53e3e"

    def test_score_100_is_high(self):
        label, _ = analytics.risk_level(100)
        assert label == "HIGH"


# ──────────────────────────────────────────────────────────────────────────────
# trend
# ──────────────────────────────────────────────────────────────────────────────

class TestTrend:
    def test_fewer_than_4_values_is_stable(self):
        assert analytics.trend([10, 50, 90]) == "stable"

    def test_strictly_increasing_is_rising(self):
        assert analytics.trend([10, 30, 50, 70, 90]) == "rising"

    def test_strictly_decreasing_is_falling(self):
        assert analytics.trend([90, 70, 50, 30, 10]) == "falling"

    def test_constant_is_stable(self):
        assert analytics.trend([50, 50, 50, 50, 50]) == "stable"

    def test_noisy_flat_is_stable(self):
        assert analytics.trend([51, 49, 50, 51, 49]) == "stable"

    def test_empty_list_is_stable(self):
        assert analytics.trend([]) == "stable"
