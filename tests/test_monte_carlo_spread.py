"""
test_monte_carlo_spread.py — Tests for the vectorized MC spread engine.

Key design decisions (from user review):
- vectorized vs scalar tolerance: 1e-6 (not 1e-8), because floating-point
  accumulation across the two separate code paths (class method vs NumPy
  broadcasting) can produce O(1e-7) differences.  The important property is
  functional equivalence, not bit-perfect identity.
- mc_scenarios fixture: 500 rows with enough column variance for sensitivity
  normalization to be stable.
"""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.lng_economics import LNGCalculator
from src.monte_carlo_spread import (
    resolve_route_constants,
    vectorized_netback,
    compute_optimal_strategy,
    compute_distribution_stats,
    sensitivity_analysis,
    compute_jera_domestic_margin,
    MCRouteResult,
)


# ---------------------------------------------------------------------------
# 1. Vectorized Netback vs scalar LNGCalculator (critical test)
# ---------------------------------------------------------------------------

class TestVectorizedVsScalar:
    ROUTE = "US_Gulf_to_Rotterdam"

    def test_netback_1e6_tolerance(self):
        """
        Single-scenario comparison between vectorized_netback() and
        LNGCalculator.calculate_netback().

        Tolerance is 1e-6 (not 1e-8) because the two code paths accumulate
        floating point differently even when the algebra is identical.
        The two paths are:
          Scalar: class method → Python floats, sequential operations
          Vector: NumPy broadcasting → double precision, but different order

        Both use identical input values (copied from config defaults).
        """
        hh     = 3.20
        dest_p = 11.50
        charter = config.DEFAULT_CHARTER_RATE           # 60_000
        fuel    = config.DEFAULT_FUEL_COST_PER_DAY      # 15_000
        bog_r   = config.BOIL_OFF_RATE                  # 0.0015
        delay   = 0.0                                   # no extra delay
        usd_jpy = 148.0

        # ── Scalar path ──
        calc = LNGCalculator(
            charter_rate=charter,
            fuel_cost_per_day=fuel,
            boil_off_rate=bog_r,
        )
        scalar_result = calc.calculate_netback(
            destination_price=dest_p,
            route_name=self.ROUTE,
            henry_hub_price=hh,
        )
        scalar_spread = scalar_result.arbitrage_spread

        # ── Vectorized path ──
        rc = resolve_route_constants(
            self.ROUTE,
            label="EU",
            dest_price_col="TTF_Price",
        )
        one_row = pd.DataFrame({
            "TTF_Price":    [dest_p],
            "HH_Price":     [hh],
            "Charter_Rate": [charter],
            "Fuel_Cost":    [fuel],
            "BOG_Rate":     [bog_r],
            "Voyage_Delay": [delay],
            "JKM_Price":    [dest_p],       # unused for this route
            "USD_JPY":      [usd_jpy],
        })
        vec_result = vectorized_netback(one_row, rc)
        vec_spread = float(vec_result.spread[0])

        assert scalar_spread == pytest.approx(vec_spread, rel=1e-6), (
            f"Scalar spread {scalar_spread:.8f} vs vectorized {vec_spread:.8f}: "
            f"difference = {abs(scalar_spread - vec_spread):.2e}"
        )


# ---------------------------------------------------------------------------
# 2. Real-option optimal strategy
# ---------------------------------------------------------------------------

class TestOptimalStrategy:
    def _make_route_result(self, spread_values, tce_values, label="Test"):
        """Helper: minimal MCRouteResult with pre-set spread/tce arrays."""
        rc = resolve_route_constants(
            "US_Gulf_to_Rotterdam", label=label, dest_price_col="TTF_Price"
        )
        n = len(spread_values)
        spread = np.array(spread_values, dtype=float)
        tce    = np.array(tce_values,   dtype=float)
        delivered = np.full(n, config.STANDARD_CARGO_SIZE_MMBTU * 0.98)
        rt_days   = np.full(n, 18.0)
        return MCRouteResult(
            route=rc,
            netback=spread + 3.0,
            spread=spread,
            tce=tce,
            delivered_volume=delivered,
            total_rt_days=rt_days,
        )

    def test_nogo_floor_when_all_negative(self):
        """When all route spreads < 0, every scenario picks No-Go (optimal=0)."""
        rr1 = self._make_route_result([-2.0, -3.0], [-5000.0, -8000.0], "EU")
        rr2 = self._make_route_result([-1.5, -2.0], [-4000.0, -6000.0], "AS")
        opt = compute_optimal_strategy([rr1, rr2])
        assert np.all(opt.optimal_spread == 0.0)
        assert opt.route_selection_prob["No-Go"] == pytest.approx(1.0)

    def test_picks_best_route(self):
        """For every scenario, optimal spread = max of all route spreads."""
        eu = np.array([1.0, 5.0, 2.0])
        ap = np.array([3.0, 2.0, 4.0])
        expected = np.maximum(eu, ap)

        rr1 = self._make_route_result(eu, eu * 1000, "EU")
        rr2 = self._make_route_result(ap, ap * 1000, "AP")
        opt = compute_optimal_strategy([rr1, rr2])
        np.testing.assert_allclose(opt.optimal_spread, expected, atol=1e-12)


# ---------------------------------------------------------------------------
# 3. Distribution statistics
# ---------------------------------------------------------------------------

class TestDistributionStats:
    def test_known_quantiles(self):
        """For a constant array the P5/P50/P95 should all equal the constant."""
        arr = np.full(1000, 5.0)
        stats = compute_distribution_stats(arr)
        assert stats.p05    == pytest.approx(5.0)
        assert stats.median == pytest.approx(5.0)
        assert stats.p95    == pytest.approx(5.0)
        assert stats.prob_positive == pytest.approx(1.0)

    def test_prob_positive_half(self):
        """Symmetric around zero → P(>0) ≈ 50%."""
        arr = np.linspace(-10, 10, 10001)
        stats = compute_distribution_stats(arr)
        assert stats.prob_positive == pytest.approx(0.5, abs=0.01)


# ---------------------------------------------------------------------------
# 4. Sensitivity normalization
# ---------------------------------------------------------------------------

class TestSensitivity:
    def test_contributions_sum_to_100(self, mc_scenarios):
        """Squared Spearman contributions (normalized) must sum to 100%."""
        # Use a simple linear spread to guarantee all factors have nonzero variance
        spread = mc_scenarios["JKM_Price"].values - mc_scenarios["HH_Price"].values
        results = sensitivity_analysis(mc_scenarios, spread)
        total = sum(r.variance_contribution_pct for r in results)
        assert total == pytest.approx(100.0, abs=0.1)


# ---------------------------------------------------------------------------
# 5. JERA divert signal
# ---------------------------------------------------------------------------

class TestJERA:
    def test_divert_when_import_exceeds_domestic(self):
        """
        When JKM × USD_JPY > JERA_DOMESTIC_REVENUE_JPY, divert_flag = True.
        """
        # Force import cost > 1500 JPY: JKM=15, USD_JPY=120 → cost=1800
        scenarios = pd.DataFrame({
            "JKM_Price": [15.0, 12.0],
            "USD_JPY":   [120.0, 120.0],  # 15×120=1800 > 1500; 12×120=1440 < 1500
        })
        result = compute_jera_domestic_margin(scenarios)
        assert bool(result.divert_flag[0]) is True   # 1800 > 1500
        assert bool(result.divert_flag[1]) is False   # 1440 < 1500

    def test_divert_probability_range(self, mc_scenarios):
        """divert_probability ∈ [0, 1]."""
        result = compute_jera_domestic_margin(mc_scenarios)
        assert 0.0 <= result.divert_probability <= 1.0
