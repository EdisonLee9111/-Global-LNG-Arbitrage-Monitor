"""
test_swap_overlay.py — Tests for the financial swap / FFA overlay module.

Design notes (from user review):
- All tests use the real MCSpreadOutput from the `mc_output` session fixture
  (built via run_mc_spread on 500-row mc_scenarios).  No mocking.
- test_variance_reduction_positive uses 500-row scenarios with fixed seed;
  large N ensures sample mean ≈ theoretical mean so auto-mode P&L ≈ 0 mean.
"""

import numpy as np
import pytest

from src import config
from src.swap_overlay import (
    LegSpec,
    SwapSpec,
    resolve_swap_rates,
    compute_swap_pnl,
    overlay_on_spread,
    compute_hedge_effectiveness,
    run_swap_overlay,
)


# ---------------------------------------------------------------------------
# Helper: build a SwapSpec with custom per-leg settings
# ---------------------------------------------------------------------------

def _make_spec(
    hh_enabled=True,  hh_h=0.8,
    jkm_enabled=True, jkm_h=0.8,
    charter_enabled=False, charter_h=0.5,
    fx_enabled=False, fx_h=0.5,
    mode="auto",
) -> SwapSpec:
    return SwapSpec(
        mode=mode,
        hh=LegSpec(enabled=hh_enabled, hedge_ratio=hh_h),
        jkm=LegSpec(enabled=jkm_enabled, hedge_ratio=jkm_h),
        charter=LegSpec(enabled=charter_enabled, hedge_ratio=charter_h),
        fx=LegSpec(enabled=fx_enabled, hedge_ratio=fx_h),
        notional_mmbtu=config.STANDARD_CARGO_SIZE_MMBTU,
        basis_noise_std=0.0,
    )


# ---------------------------------------------------------------------------
# 1. Swap direction: HH Pay-Fixed / Receive-Float
# ---------------------------------------------------------------------------

class TestHHSwapDirection:
    def test_pnl_positive_when_hh_rises(self, mc_output, mc_scenarios):
        """
        HH swap (Pay Fixed / Receive Float):
          pnl = h_hh × (HH_spot − HH_fixed)
        When all HH_spot values are above HH_fixed, every pnl element > 0.
        """
        # Use a very low fixed rate so all spot values are above it
        fixed_rate = 0.01
        spec   = _make_spec(jkm_enabled=False)
        rates  = {"hh": fixed_rate, "jkm": 0.0, "charter": 0.0, "fx": 0.0}
        total_pnl, _ = compute_swap_pnl(
            spec, rates, mc_scenarios,
            mc_output.route_results, mc_output.optimal_strategy,
        )
        assert np.all(total_pnl > 0), (
            "All HH spots should be above near-zero fixed rate"
        )

    def test_pnl_negative_when_hh_falls(self, mc_output, mc_scenarios):
        """When all HH_spot < HH_fixed, Pay-Fixed position loses money."""
        fixed_rate = 1_000.0   # absurdly high fixed rate
        spec   = _make_spec(jkm_enabled=False)
        rates  = {"hh": fixed_rate, "jkm": 0.0, "charter": 0.0, "fx": 0.0}
        total_pnl, _ = compute_swap_pnl(
            spec, rates, mc_scenarios,
            mc_output.route_results, mc_output.optimal_strategy,
        )
        assert np.all(total_pnl < 0)


# ---------------------------------------------------------------------------
# 2. Swap direction: JKM Receive-Fixed / Pay-Float
# ---------------------------------------------------------------------------

class TestJKMSwapDirection:
    def test_pnl_positive_when_jkm_falls(self, mc_output, mc_scenarios):
        """
        JKM swap (Receive Fixed / Pay Float):
          pnl = h_jkm × (JKM_fixed − JKM_spot)
        When JKM_fixed >> JKM_spot, pnl > 0.
        """
        fixed_rate = 1_000.0   # very high fixed → JKM_fixed − spot always > 0
        spec   = _make_spec(hh_enabled=False)
        rates  = {"hh": 0.0, "jkm": fixed_rate, "charter": 0.0, "fx": 0.0}
        total_pnl, _ = compute_swap_pnl(
            spec, rates, mc_scenarios,
            mc_output.route_results, mc_output.optimal_strategy,
        )
        assert np.all(total_pnl > 0)

    def test_pnl_negative_when_jkm_rises(self, mc_output, mc_scenarios):
        """When JKM_spot >> JKM_fixed, the Receive-Fixed position loses."""
        fixed_rate = 0.01
        spec   = _make_spec(hh_enabled=False)
        rates  = {"hh": 0.0, "jkm": fixed_rate, "charter": 0.0, "fx": 0.0}
        total_pnl, _ = compute_swap_pnl(
            spec, rates, mc_scenarios,
            mc_output.route_results, mc_output.optimal_strategy,
        )
        assert np.all(total_pnl < 0)


# ---------------------------------------------------------------------------
# 3. Hedge ratio = 0 → hedged spread == unhedged spread
# ---------------------------------------------------------------------------

class TestHedgeRatioZero:
    def test_zero_ratio_is_passthrough(self, mc_output, mc_scenarios):
        """h=0 on all legs → total_pnl = 0, hedged == unhedged."""
        spec  = _make_spec(hh_h=0.0, jkm_h=0.0)
        rates = resolve_swap_rates(spec, mc_scenarios)
        total_pnl, rt_days = compute_swap_pnl(
            spec, rates, mc_scenarios,
            mc_output.route_results, mc_output.optimal_strategy,
        )
        np.testing.assert_allclose(total_pnl, 0.0, atol=1e-10)


# ---------------------------------------------------------------------------
# 4. Auto mode: swap rate = MC mean
# ---------------------------------------------------------------------------

class TestAutoModeRate:
    def test_rate_equals_mc_mean(self, mc_output, mc_scenarios):
        """In auto mode, resolved HH swap rate == mean(HH_Price column)."""
        spec  = _make_spec()
        rates = resolve_swap_rates(spec, mc_scenarios)
        expected_hh_mean = float(mc_scenarios["HH_Price"].mean())
        assert rates["hh"] == pytest.approx(expected_hh_mean, rel=1e-9)

        expected_jkm_mean = float(mc_scenarios["JKM_Price"].mean())
        assert rates["jkm"] == pytest.approx(expected_jkm_mean, rel=1e-9)


# ---------------------------------------------------------------------------
# 5. Variance reduction with default hedging (80% HH + JKM)
# ---------------------------------------------------------------------------

class TestVarianceReduction:
    def test_default_hedge_reduces_variance(self, mc_output):
        """
        With 80% HH and JKM hedging in auto mode, the hedged distribution
        should have strictly lower variance than the unhedged optimal spread.

        Uses the full run_swap_overlay() path on the session mc_output
        (500-row scenarios, fixed seed) which ensures sample mean ≈ fair value.
        """
        hedged = run_swap_overlay(mc_output=mc_output, output_dir=None)
        eff = hedged.effectiveness
        assert eff.variance_reduction > 0, (
            f"Expected positive variance reduction, got {eff.variance_reduction:.4f}"
        )
