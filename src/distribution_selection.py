"""
distribution_selection.py - Step 2 distribution family selection
================================================================
Selects distribution families for uncertain Netback inputs and
estimates practical parameters from current data.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Tuple
import math
import os

import numpy as np
import pandas as pd

from . import config


@dataclass
class DistributionRow:
    """Single row describing one parameter's distribution choice."""

    parameter: str
    distribution_family: str
    support: str
    key_parameters: str
    horizon_note: str
    implementation_note: str


def _format_markdown_table(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    return "\n".join(lines)


def _estimate_ou_params(series: pd.Series) -> Dict[str, float]:
    """
    Estimate OU parameters with discrete regression:
        X_{t+1} = a + b * X_t + eps
    """
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if len(clean) < 30:
        return {"s0": float(clean.iloc[-1]), "kappa": math.nan, "theta": float(clean.mean()), "sigma": math.nan}

    x_t = clean.iloc[:-1].values
    x_tp1 = clean.iloc[1:].values

    # OLS by numpy polyfit: x_tp1 = b*x_t + a
    b, a = np.polyfit(x_t, x_tp1, 1)
    residuals = x_tp1 - (a + b * x_t)
    sigma_eps = float(np.std(residuals, ddof=1))

    # Daily step dt = 1
    if b <= 0 or b >= 0.9999:
        kappa = 0.03
    else:
        kappa = float(-np.log(b))
    theta = float(a / (1 - b)) if abs(1 - b) > 1e-8 else float(clean.mean())

    # Convert discrete residual std to continuous OU sigma
    if kappa <= 0:
        sigma = sigma_eps
    else:
        denom = max(1 - np.exp(-2 * kappa), 1e-10)
        sigma = float(sigma_eps * np.sqrt(2 * kappa / denom))

    return {
        "s0": float(clean.iloc[-1]),
        "kappa": float(max(kappa, 1e-6)),
        "theta": theta,
        "sigma": float(max(sigma, 1e-6)),
    }


def _estimate_gbm_params(series: pd.Series) -> Dict[str, float]:
    """Estimate GBM-like daily drift/vol from log returns."""
    clean = pd.to_numeric(series, errors="coerce").dropna()
    clean = clean[clean > 0]
    if len(clean) < 10:
        s0 = float(clean.iloc[-1]) if len(clean) else math.nan
        return {"s0": s0, "mu_daily": math.nan, "sigma_daily": math.nan}

    lr = np.log(clean / clean.shift(1)).dropna()
    sigma_daily = float(lr.std(ddof=1))
    mu_daily = float(lr.mean() + 0.5 * sigma_daily * sigma_daily)
    return {"s0": float(clean.iloc[-1]), "mu_daily": mu_daily, "sigma_daily": sigma_daily}


def _build_price_rows(market_data: pd.DataFrame, horizon_days: Tuple[int, int]) -> List[DistributionRow]:
    out: List[DistributionRow] = []
    low_h, high_h = horizon_days
    for col, label in [("HH_Price", "HH price"), ("TTF_Price", "TTF price"), ("JKM_Price", "JKM price")]:
        ou = _estimate_ou_params(market_data[col])
        gbm = _estimate_gbm_params(market_data[col])
        out.append(
            DistributionRow(
                parameter=label,
                distribution_family="OU mean-reversion (primary), Lognormal/GBM (fallback)",
                support="Price > 0",
                key_parameters=(
                    f"S0={ou['s0']:.2f}, kappa={ou['kappa']:.4f}, theta={ou['theta']:.2f}, sigma_ou={ou['sigma']:.4f}; "
                    f"mu_gbm={gbm['mu_daily']:.6f}/day, sigma_gbm={gbm['sigma_daily']:.6f}/day"
                ),
                horizon_note=f"Project from t0 to discharge horizon T={low_h}-{high_h} days",
                implementation_note="Use OU transition for gas-specific mean reversion; keep GBM as stress/fallback",
            )
        )
    return out


def _charter_distribution_row(current_rate: float | None = None) -> DistributionRow:
    """
    Parameters
    ----------
    current_rate : float or None
        Live market charter rate (e.g. Spark25s spot quote).
        Falls back to config.DEFAULT_CHARTER_RATE only when unavailable.
    """
    current = float(current_rate if current_rate is not None else config.DEFAULT_CHARTER_RATE)
    source = "live market input" if current_rate is not None else "config fallback"
    # Regime-aware practical parameterization
    if current <= 70_000:
        regime = "low season"
        sigma_ln = 0.35
        jump_lambda = 0.04
        jump_mean = 0.30
    elif current <= 100_000:
        regime = "mid regime"
        sigma_ln = 0.45
        jump_lambda = 0.06
        jump_mean = 0.35
    else:
        regime = "peak regime"
        sigma_ln = 0.60
        jump_lambda = 0.10
        jump_mean = 0.45

    mu_ln = math.log(current) - 0.5 * sigma_ln * sigma_ln
    return DistributionRow(
        parameter="Charter rate",
        distribution_family="Lognormal (base) + optional jump mean-reversion",
        support="Rate > 0, right-skewed",
        key_parameters=(
            f"S0={current:,.0f} USD/day ({source}), regime={regime}, mu_ln={mu_ln:.4f}, sigma_ln={sigma_ln:.3f}, "
            f"jump_lambda~{jump_lambda:.2f}/period, jump_mean~{jump_mean:.2f}"
        ),
        horizon_note="Model over same cargo horizon (30-60 days), initialize from current market regime",
        implementation_note="Captures non-negativity and upside spikes (e.g., >200k/day in tight markets)",
    )


def _fuel_cost_distribution_row(
    current_fuel_cost: float | None = None,
    market_data: pd.DataFrame | None = None,
) -> DistributionRow:
    """
    Fuel cost distribution.

    Parameters
    ----------
    current_fuel_cost : float or None
        Live bunker cost (USD/day). Falls back to config constant.
    market_data : pd.DataFrame or None
        If provided and contains HH_Price, notes the implicit correlation
        for LNG-fuelled vessels (MEGI / X-DF).
    """
    current = float(
        current_fuel_cost if current_fuel_cost is not None
        else config.DEFAULT_FUEL_COST_PER_DAY
    )
    source = "live market input" if current_fuel_cost is not None else "config fallback"

    sigma_ln = 0.30
    mu_ln = math.log(current) - 0.5 * sigma_ln * sigma_ln

    corr_note = ""
    if market_data is not None and "HH_Price" in market_data.columns:
        corr_note = (
            "; for MEGI/X-DF LNG-fuelled vessels fuel cost is correlated "
            "with HH/JKM price -- model as rho(fuel, gas_price) in joint simulation"
        )

    return DistributionRow(
        parameter="Fuel cost",
        distribution_family="Lognormal (tracks VLSFO/LSMGO bunker prices)",
        support="Cost > 0",
        key_parameters=(
            f"S0={current:,.0f} USD/day ({source}), "
            f"mu_ln={mu_ln:.4f}, sigma_ln={sigma_ln:.3f}"
            f"{corr_note}"
        ),
        horizon_note="Same cargo horizon (30-60 days); co-moves with oil/gas benchmarks",
        implementation_note=(
            "~20% of total shipping cost; hidden correlation source for LNG-fuelled vessels"
        ),
    )


def _voyage_delay_row() -> DistributionRow:
    month = datetime.now().month
    dry_season = month in (1, 2, 3, 4)
    panama_shift = 3.0 if dry_season else 0.0

    return DistributionRow(
        parameter="Voyage days (delay component)",
        distribution_family="Shifted Gamma for extra delay",
        support="Extra delay >= 0",
        key_parameters=(
            "Base days deterministic by distance/speed; "
            "Delay ~ Gamma(k=2.0, theta=1.5) days; "
            f"Panama dry-season shift={panama_shift:.1f} day(s)"
        ),
        horizon_note="Total voyage days = deterministic base + random delay",
        implementation_note="Right-skew handles weather/queue/congestion; dry-season Panama handled by shift",
    )


def _bog_row() -> DistributionRow:
    low = 0.0008
    high = 0.0015
    mode = float(np.clip(config.BOIL_OFF_RATE, low + 1e-6, high - 1e-6))
    m = (mode - low) / (high - low)
    strength = 20.0
    alpha = 1 + m * (strength - 2)
    beta = 1 + (1 - m) * (strength - 2)

    return DistributionRow(
        parameter="BOG boil-off rate",
        distribution_family="Scaled Beta on [0.08%, 0.15%] (or triangular simplification)",
        support="0.0008 <= rate <= 0.0015",
        key_parameters=(
            f"low={low:.4%}, high={high:.4%}, mode={mode:.4%}, "
            f"beta(alpha={alpha:.2f}, beta={beta:.2f})"
        ),
        horizon_note="Low-impact in v1; can stay fixed in core simulation and move to sensitivity layer",
        implementation_note="Beta enforces bounded support; triangular(min, mode, max) is lightweight fallback",
    )


def _fx_row(market_data: pd.DataFrame, horizon_days: Tuple[int, int]) -> DistributionRow:
    clean = pd.to_numeric(market_data["USD_JPY"], errors="coerce").dropna()
    lr = np.log(clean / clean.shift(1)).dropna()
    mu = float(lr.mean()) if len(lr) else math.nan
    sigma = float(lr.std(ddof=1)) if len(lr) > 1 else math.nan
    s0 = float(clean.iloc[-1]) if len(clean) else math.nan
    low_h, high_h = horizon_days

    return DistributionRow(
        parameter="USD/JPY",
        distribution_family="Normal on returns (base), Lognormal on level (equivalent transform)",
        support="Return in R; level > 0",
        key_parameters=f"S0={s0:.2f}, mu_ret={mu:.6f}/day, sigma_ret={sigma:.6f}/day (replace sigma with option IV when available)",
        horizon_note=f"Scale to T={low_h}-{high_h} days: mean~mu*T, vol~sigma*sqrt(T)",
        implementation_note=(
            "Must-model in v1: JPY depreciation raises real cost for Japanese buyers, "
            "suppressing spot JKM demand; JPY appreciation does the opposite. "
            "Include in joint simulation with price factors. "
            "If FX option implied vol is available, override historical sigma for forward-looking risk"
        ),
    )


def build_step2_distribution_selection(
    market_data: pd.DataFrame,
    output_dir: str = config.OUTPUT_DIR,
    horizon_days: Tuple[int, int] = (30, 60),
    current_charter_rate: float | None = None,
    current_fuel_cost: float | None = None,
) -> Dict[str, object]:
    """
    Build and persist Step 2 output: distribution-family choices by parameter.

    Parameters
    ----------
    current_charter_rate : float or None
        Live market charter rate (USD/day). Falls back to config constant.
    current_fuel_cost : float or None
        Live market fuel cost (USD/day). Falls back to config constant.
    """
    rows: List[DistributionRow] = []
    rows.extend(_build_price_rows(market_data, horizon_days=horizon_days))
    rows.append(_charter_distribution_row(current_rate=current_charter_rate))
    rows.append(_fuel_cost_distribution_row(
        current_fuel_cost=current_fuel_cost,
        market_data=market_data,
    ))
    rows.append(_voyage_delay_row())
    rows.append(_bog_row())
    rows.append(_fx_row(market_data, horizon_days=horizon_days))

    df = pd.DataFrame([asdict(r) for r in rows])

    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "step2_distribution_selection.csv")
    md_path = os.path.join(output_dir, "step2_distribution_selection.md")
    df.to_csv(csv_path, index=False)

    md_lines = [
        "# Step 2 - Distribution Family Selection (Auto Generated)",
        "",
        "Goal: choose distribution/process families for uncertain Netback drivers and parameterize them for 30-60 day horizon.",
        "",
        "## Distribution Plan",
        "",
        _format_markdown_table(df),
        "",
        "## Notes",
        "",
        "- Price variables prefer OU mean reversion for gas economics, with GBM/lognormal as fallback stress view.",
        "- Charter rate uses positive right-skew family with optional jump behavior for peak-season spikes.",
        "- Delay component is modeled separately from deterministic base voyage days.",
        "- BOG is bounded and low-impact; suitable for bounded distributions or sensitivity-only treatment in v1.",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return {
        "distribution_df": df,
        "csv_path": csv_path,
        "md_path": md_path,
        "horizon_days": horizon_days,
    }
