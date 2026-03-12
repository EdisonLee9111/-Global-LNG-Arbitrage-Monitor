"""
conftest.py — Shared pytest fixtures for LNG Arbitrage Monitor tests.

All fixtures are self-contained (no network calls, no disk I/O beyond /tmp).

Key design decisions (from user review):
- market_data: 60 synthetic rows with realistic ranges
- mc_scenarios: 500 rows with fixed seed to guarantee stable column variances
- mc_output_fixture: real MCSpreadOutput from run_mc_spread() — not mocked —
  so swap_overlay tests exercise the full integration path
"""

import math
import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta

from src import config
from src.lng_economics import LNGCalculator
from src.monte_carlo_spread import run_mc_spread, MCSpreadOutput


# ---------------------------------------------------------------------------
# Helper: deterministic date index
# ---------------------------------------------------------------------------

def _date_range(n: int) -> pd.DatetimeIndex:
    start = pd.Timestamp("2024-01-02")
    return pd.bdate_range(start=start, periods=n)


# ---------------------------------------------------------------------------
# Fixture: synthetic market data (60 business-day rows)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def market_data() -> pd.DataFrame:
    """
    Minimal synthetic market data with all four required columns.
    Values are physically plausible (but not real historical data).
    """
    rng = np.random.default_rng(seed=42)
    n = 60

    hh  = 3.00 + rng.normal(0, 0.15, n).cumsum() * 0.1 + 3.00
    hh  = np.clip(hh, 1.5, 6.0)
    ttf = 10.00 + rng.normal(0, 0.30, n).cumsum() * 0.05 + 10.00
    ttf = np.clip(ttf, 4.0, 18.0)
    jkm = ttf + 1.5 + rng.normal(0, 0.20, n)
    jkm = np.clip(jkm, 4.0, 22.0)
    usd_jpy = 148.0 + rng.normal(0, 0.5, n).cumsum() * 0.2
    usd_jpy = np.clip(usd_jpy, 130.0, 165.0)

    df = pd.DataFrame(
        {
            "HH_Price":  hh,
            "TTF_Price": ttf,
            "JKM_Price": jkm,
            "USD_JPY":   usd_jpy,
        },
        index=_date_range(n),
    )
    df.index.name = "Date"
    return df


# ---------------------------------------------------------------------------
# Fixture: LNGCalculator with default config params
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def calculator() -> LNGCalculator:
    return LNGCalculator(
        cargo_size_mmbtu=config.STANDARD_CARGO_SIZE_MMBTU,
        charter_rate=config.DEFAULT_CHARTER_RATE,
        fuel_cost_per_day=config.DEFAULT_FUEL_COST_PER_DAY,
        liquefaction_cost=config.DEFAULT_LIQUEFACTION_COST,
        boil_off_rate=config.BOIL_OFF_RATE,
    )


# ---------------------------------------------------------------------------
# Fixture: 500-row MC scenario DataFrame (Copula-free for unit test speed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mc_scenarios() -> pd.DataFrame:
    """
    500 correlated-like scenario rows with all columns required by the MC engine.

    Required columns:
        HH_Price, TTF_Price, JKM_Price, Charter_Rate, Fuel_Cost,
        Voyage_Delay, BOG_Rate, USD_JPY

    N=500 ensures enough variance in each column that sensitivity normalization
    and variance-reduction assertions are stable (per user review feedback).
    Fixed seed=2026 for reproducibility.
    """
    rng = np.random.default_rng(seed=2026)
    n = 500

    hh  = rng.normal(loc=3.0,   scale=0.5,      size=n).clip(1.5, 8.0)
    ttf = hh + rng.normal(loc=7.0, scale=1.5,   size=n).clip(0.5, 15.0)
    jkm = ttf + rng.normal(loc=1.5, scale=0.5,  size=n).clip(0.3, 5.0)

    charter = np.exp(rng.normal(np.log(60_000), 0.35, n)).clip(20_000, 200_000)
    fuel    = np.exp(rng.normal(np.log(15_000), 0.25, n)).clip(5_000,  60_000)
    delay   = rng.gamma(shape=2.0, scale=1.5, size=n)
    bog     = rng.uniform(0.0008, 0.0015, n)
    usd_jpy = rng.normal(148.0, 5.0, n).clip(125.0, 165.0)

    return pd.DataFrame({
        "HH_Price":    hh,
        "TTF_Price":   ttf,
        "JKM_Price":   jkm,
        "Charter_Rate": charter,
        "Fuel_Cost":   fuel,
        "Voyage_Delay": delay,
        "BOG_Rate":    bog,
        "USD_JPY":     usd_jpy,
    })


# ---------------------------------------------------------------------------
# Fixture: full MCSpreadOutput built from mc_scenarios (session-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def mc_output(mc_scenarios) -> MCSpreadOutput:
    """
    Real MCSpreadOutput (no mocking).  Used by swap_overlay tests which need
    authentic route_results and optimal_strategy objects.

    output_dir=None to avoid writing any files during tests.
    """
    return run_mc_spread(scenarios=mc_scenarios, output_dir=None)
