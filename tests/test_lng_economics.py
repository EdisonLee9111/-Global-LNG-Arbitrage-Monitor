"""
test_lng_economics.py — Unit tests for LNGCalculator core formulas.

Tests assert raw formula semantics against known-good scalar values.
Following user feedback: asserting against result.netback directly
avoids reimplementing the shipping / canal denominator split.
"""

import math
import pytest
from src import config
from src.lng_economics import LNGCalculator


# ---------------------------------------------------------------------------
# Voyage days
# ---------------------------------------------------------------------------

class TestVoyageDays:
    def test_formula(self, calculator):
        """days = distance / (speed × 24)"""
        distance_nm = 5_000.0
        speed_knots = 17.0
        expected = distance_nm / (speed_knots * 24.0)
        result = calculator.calculate_voyage_days(distance_nm, speed_knots)
        assert math.isclose(result, expected, rel_tol=1e-12)

    def test_zero_speed_raises(self, calculator):
        with pytest.raises(ValueError):
            calculator.calculate_voyage_days(5_000.0, 0.0)

    def test_negative_speed_raises(self, calculator):
        with pytest.raises(ValueError):
            calculator.calculate_voyage_days(5_000.0, -5.0)


# ---------------------------------------------------------------------------
# Boil-off gas exponential decay
# ---------------------------------------------------------------------------

class TestBoilOff:
    def test_exponential_decay(self, calculator):
        """V_loss = V0 × [1 - (1 - r)^d]"""
        v0 = 1_000.0
        rate = 0.0015
        days = 10.0
        expected_loss = v0 * (1 - (1 - rate) ** days)
        loss = calculator.calculate_boil_off_loss(v0, days, boil_off_rate=rate)
        assert math.isclose(loss, expected_loss, rel_tol=1e-12)

    def test_zero_rate_gives_no_loss(self, calculator):
        """BOG rate = 0 → zero evaporation loss"""
        loss = calculator.calculate_boil_off_loss(1_000.0, 20.0, boil_off_rate=0.0)
        assert loss == pytest.approx(0.0, abs=1e-12)

    def test_large_days_approaches_full_cargo(self, calculator):
        """After many days at constant rate the cargo asymptotes to 0."""
        loss = calculator.calculate_boil_off_loss(1_000.0, 10_000.0, boil_off_rate=0.0015)
        assert loss == pytest.approx(1_000.0, rel=1e-3)


# ---------------------------------------------------------------------------
# Netback value and trading signals
# ---------------------------------------------------------------------------

class TestNetback:
    ROUTE = "US_Gulf_to_Rotterdam"

    def test_netback_positive_spread_is_arb_open(self, calculator):
        """A high destination price should yield Netback > HH (arb open)."""
        result = calculator.calculate_netback(
            destination_price=15.0,
            route_name=self.ROUTE,
            henry_hub_price=3.0,
            destination_label="Test EU",
        )
        assert result.is_arb_open is True
        assert result.arbitrage_spread > 0

    def test_netback_low_price_closes_arb(self, calculator):
        """A very low destination price should close the arb window."""
        result = calculator.calculate_netback(
            destination_price=4.0,
            route_name=self.ROUTE,
            henry_hub_price=3.5,
        )
        # With shipping costs ~$2–3/MMBtu, a $4 dest price minus costs < $3.5 HH
        assert result.is_arb_open is False
        assert result.arbitrage_spread < 0

    def test_signal_strong_buy_threshold(self, calculator):
        """spread > $1.0 → STRONG BUY in signal text."""
        result = calculator.calculate_netback(
            destination_price=20.0,  # very high
            route_name=self.ROUTE,
            henry_hub_price=2.0,
        )
        assert result.arbitrage_spread > 1.0
        assert "STRONG BUY" in result.signal

    def test_signal_no_arb_threshold(self, calculator):
        """Closed arb window → NO ARB in signal text."""
        result = calculator.calculate_netback(
            destination_price=3.0,  # too low
            route_name=self.ROUTE,
            henry_hub_price=3.5,
        )
        assert "NO ARB" in result.signal

    def test_netback_components_sum(self, calculator):
        """
        Netback = dest × (1 - BOG_ratio) - shipping_per_mmbtu - liq.
        Since NetbackResult.shipping_cost_per_mmbtu already includes canal fee,
        we verify the identity: netback + shipping + liq = dest × (1 - bog_ratio).
        """
        dest_price = 12.0
        result = calculator.calculate_netback(
            destination_price=dest_price,
            route_name=self.ROUTE,
            henry_hub_price=3.0,
        )
        # Recompute the deliverable-price side
        voyage = calculator.calculate_voyage(self.ROUTE)
        bog_loss = calculator.calculate_boil_off_loss(
            calculator.cargo_size_mmbtu, voyage.laden_days
        )
        bog_ratio = bog_loss / calculator.cargo_size_mmbtu
        revenue_side = dest_price * (1 - bog_ratio)

        lhs = result.netback + result.shipping_cost_per_mmbtu + result.liquefaction_cost
        assert lhs == pytest.approx(revenue_side, rel=1e-9)
