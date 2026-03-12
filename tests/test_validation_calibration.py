"""
test_validation_calibration.py — Tests for range checks and inverse CDFs.

Design notes (from user review):
- test_range_check_warn: WARN triggers when >2% of draws are out of bounds.
  With 100 rows we need at least 3 out-of-bounds values (3%).
  → We inject 5 out-of-bounds values in 100 rows = 5%.
- test_range_check_pass: values firmly within bounds → PASS.
"""

import numpy as np
import pandas as pd
import pytest

from src.validation_calibration import (
    run_range_checks,
    _inv_cdf_ou,
    _inv_cdf_lognormal,
    PHYSICAL_BOUNDS,
)


# ---------------------------------------------------------------------------
# 1. Range checks
# ---------------------------------------------------------------------------

class TestRangeChecks:
    def test_pass_when_within_bounds(self):
        """Values firmly within physical bounds → PASS status."""
        n = 200
        # HH physical bounds: (0.50, 50.0)
        hh_vals = np.full(n, 3.0)   # well within [0.5, 50]
        df = pd.DataFrame({"HH_Price": hh_vals})
        results = run_range_checks(df)
        assert len(results) == 1
        assert results[0].status == "PASS"

    def test_warn_when_enough_out_of_bounds(self):
        """
        5 out-of-range values in 100 rows = 5% → WARN (threshold is >2%).
        Per user review: must be >2% to trigger, so ≥3/100.
        """
        n = 100
        # HH physical bounds: (0.50, 50.0)
        hh_vals = np.full(n, 3.0)
        # Inject 5 values below the lower bound (0.5)
        hh_vals[:5] = 0.01
        df = pd.DataFrame({"HH_Price": hh_vals})
        results = run_range_checks(df)
        assert results[0].status == "WARN", (
            f"Expected WARN but got {results[0].status}. "
            f"pct_below_low={results[0].pct_below_low:.2f}%"
        )
        assert results[0].pct_below_low == pytest.approx(5.0, abs=0.1)

    def test_no_bounds_for_unknown_column(self):
        """An unknown column has no PHYSICAL_BOUNDS → PASS by default."""
        df = pd.DataFrame({"UnknownParam": np.random.uniform(0, 1, 100)})
        results = run_range_checks(df)
        # Should not raise; status is PASS since bounds are (-inf, inf)
        assert results[0].status == "PASS"


# ---------------------------------------------------------------------------
# 2. Inverse CDFs produce physically valid values
# ---------------------------------------------------------------------------

class TestInverseCDF:
    def test_ou_cdf_positive_prices(self):
        """
        OU inverse CDF must produce prices > the floor (default 1e-4),
        even when the OU distribution could theoretically go negative.
        """
        params = {
            "s0": 3.0, "kappa": 0.03, "theta": 3.0, "sigma": 0.5
        }
        # Use uniforms spread across (0.001, 0.999)
        u = np.linspace(0.001, 0.999, 200)
        prices = _inv_cdf_ou(u, params, T=45)
        assert np.all(prices >= 1e-4), (
            f"OU inverse CDF returned negative/zero prices: min={prices.min():.6f}"
        )

    def test_lognormal_cdf_positive_prices(self):
        """Lognormal inverse CDF must always produce positive values."""
        params = {
            "s0": 60_000.0,
            "sigma_daily": 0.35 / (252 ** 0.5),
            "mu_daily": 0.0,
        }
        u = np.linspace(0.001, 0.999, 200)
        prices = _inv_cdf_lognormal(u, params, T=45)
        assert np.all(prices > 0)

    def test_ou_extreme_quantiles_stay_bounded(self):
        """
        At p=0.01 and p=0.99, OU CDF should produce values within a
        physically reasonable range (not NaN or ±inf).
        """
        params = {
            "s0": 10.0, "kappa": 0.02, "theta": 10.0, "sigma": 1.0
        }
        u = np.array([0.01, 0.99])
        prices = _inv_cdf_ou(u, params, T=45)
        assert np.all(np.isfinite(prices))
        assert np.all(prices > 0)
