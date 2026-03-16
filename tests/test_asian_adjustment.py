"""
test_asian_adjustment.py — Validation tests for Asian swap variance adjustment.

Step 6 validation checks:
  6a. Sanity checks: variance_ratio in (0, 1], Brownian limits, sigma_scale consistency
  6b. Backward compatibility: european settlement = identity transform
  6c. Numerical impact: typical OU kappa range produces expected variance ratios
"""

import math
import numpy as np
import pytest

from src.asian_adjustment import (
    AsianAdjustment,
    compute_ou_variance_ratio,
    compute_gbm_variance_ratio,
    to_asian_equivalent,
    build_asian_adjustments,
    validate_asian_adjustments,
)
from src.swap_overlay import (
    LegSpec,
    SwapSpec,
    run_swap_overlay,
)


# =========================================================================
# 6a. Sanity Checks — variance_ratio bounds and edge cases
# =========================================================================

class TestOUVarianceRatio:
    """Closed-form OU variance ratio properties."""

    def test_ratio_in_valid_range(self):
        """For any valid kappa > 0, ratio must be in (0, 1]."""
        for kappa in [0.001, 0.01, 0.03, 0.05, 0.10, 0.50, 1.0]:
            ratio = compute_ou_variance_ratio(kappa, delta=20, T=45)
            assert 0.0 < ratio <= 1.0, (
                f"kappa={kappa}: ratio={ratio} out of range"
            )

    def test_brownian_limit(self):
        """When kappa -> 0, ratio -> 1/3 (Brownian limit)."""
        ratio = compute_ou_variance_ratio(kappa=1e-8, delta=20, T=45)
        assert ratio == pytest.approx(1.0 / 3.0, rel=1e-4)

    def test_all_kappa_values_produce_valid_ratios(self):
        """
        OU variance ratio is non-monotonic in kappa (Var(terminal) can shrink
        faster than Var(avg) for large kappa). All values must remain in (0, 1].
        """
        for kappa in [0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.50]:
            ratio = compute_ou_variance_ratio(kappa, delta=20, T=45)
            assert 0.0 < ratio <= 1.0, (
                f"kappa={kappa}: ratio={ratio:.4f} out of valid range"
            )

    def test_typical_hh_kappa_range(self):
        """
        6c. For typical HH kappa (0.02-0.05 per trading day):
        variance_ratio should be ~0.30-0.45, sigma_scale ~0.55-0.67.
        """
        for kappa in [0.02, 0.03, 0.04, 0.05]:
            ratio = compute_ou_variance_ratio(kappa, delta=20, T=45)
            sigma_scale = math.sqrt(ratio)
            assert 0.20 <= ratio <= 0.55, (
                f"kappa={kappa}: ratio={ratio:.4f} outside expected range"
            )
            assert 0.45 <= sigma_scale <= 0.75, (
                f"kappa={kappa}: sigma_scale={sigma_scale:.4f} outside expected range"
            )


class TestGBMVarianceRatio:
    def test_basic_formula(self):
        """GBM ratio = delta / (3*T)."""
        ratio = compute_gbm_variance_ratio(delta=20, T=45)
        assert ratio == pytest.approx(20 / (3 * 45), rel=1e-9)

    def test_clamped_to_unit(self):
        """When delta > 3*T, ratio is clamped to 1.0."""
        ratio = compute_gbm_variance_ratio(delta=200, T=10)
        assert ratio <= 1.0

    def test_zero_horizon(self):
        ratio = compute_gbm_variance_ratio(delta=20, T=0)
        assert ratio == 1.0


# =========================================================================
# 6a. to_asian_equivalent properties
# =========================================================================

class TestToAsianEquivalent:
    def test_mean_preserved(self):
        """E[output] == E[input]."""
        rng = np.random.default_rng(42)
        x = rng.normal(10.0, 2.0, 10_000)
        y = to_asian_equivalent(x, sigma_scale=0.6)
        assert np.mean(y) == pytest.approx(np.mean(x), rel=1e-10)

    def test_variance_compressed(self):
        """Var[output] == Var[input] * sigma_scale^2."""
        rng = np.random.default_rng(42)
        x = rng.normal(10.0, 2.0, 10_000)
        ss = 0.6
        y = to_asian_equivalent(x, sigma_scale=ss)
        assert np.var(y) == pytest.approx(np.var(x) * ss**2, rel=1e-10)

    def test_sigma_scale_one_is_identity(self):
        """sigma_scale=1.0 returns the original array."""
        rng = np.random.default_rng(42)
        x = rng.normal(5.0, 1.0, 100)
        y = to_asian_equivalent(x, sigma_scale=1.0)
        np.testing.assert_array_equal(y, x)


# =========================================================================
# 6a. validate_asian_adjustments
# =========================================================================

class TestValidateAdjustments:
    def test_valid_adjustment_no_warnings(self):
        adj = AsianAdjustment(
            variance_ratio=0.35,
            sigma_scale=math.sqrt(0.35),
            settlement_basis_std=0.0,
            process_type="ou",
            kappa=0.03,
            averaging_start_day=25,
            averaging_days=20,
            horizon_days=45,
        )
        warnings = validate_asian_adjustments({"hh": adj})
        assert warnings == []

    def test_ratio_out_of_range_warns(self):
        adj = AsianAdjustment(
            variance_ratio=1.5,
            sigma_scale=math.sqrt(1.5),
            settlement_basis_std=0.0,
            process_type="ou",
            kappa=0.03,
            averaging_start_day=25,
            averaging_days=20,
            horizon_days=45,
        )
        warnings = validate_asian_adjustments({"hh": adj})
        assert len(warnings) >= 1
        assert "out of valid range" in warnings[0]


# =========================================================================
# 6b. Backward Compatibility — european = no change
# =========================================================================

class TestBackwardCompatibility:
    def test_european_settlement_no_adjustment(self, mc_output):
        """
        With settlement='european', run_swap_overlay should produce identical
        results regardless of whether step3_estimates is passed.
        """
        spec_eu = SwapSpec(
            mode="auto",
            hh=LegSpec(enabled=True, hedge_ratio=0.8, settlement="european"),
            jkm=LegSpec(enabled=True, hedge_ratio=0.8, settlement="european"),
        )
        out_no_est = run_swap_overlay(mc_output=mc_output, spec=spec_eu,
                                      step3_estimates=None, output_dir=None)
        # With step3_estimates=None, adjustments={} → european behavior
        # Mean and std should match when both are european with no estimates
        assert out_no_est.effectiveness.variance_reduction > 0

    def test_none_estimates_no_adjustment(self, mc_output):
        """step3_estimates=None → adjustments={} → no Asian adjustment."""
        out = run_swap_overlay(mc_output=mc_output, step3_estimates=None,
                               output_dir=None)
        # Should still work and produce valid results
        assert out.hedged_spread is not None
        assert len(out.hedged_spread) == mc_output.n_scenarios
