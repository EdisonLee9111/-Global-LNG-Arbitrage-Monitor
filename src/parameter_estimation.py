"""
parameter_estimation.py - Step 3 parameter estimation
=====================================================
Estimates concrete numerical parameters for each distribution family
selected in Step 2.  Three estimation sources are supported:

    A. historical  – derive from market_data time series
    B. implied      – use option-implied vol (placeholder; plug in when data available)
    C. manual       – expert/trader sets min, mode, max → triangular / PERT

The default pipeline uses *historical* and exposes an override dict so a
trader can surgically replace any sub-parameter.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd

from . import config
from .distribution_selection import _estimate_ou_params, _estimate_gbm_params


# ── core data structure ──────────────────────────────────────────────

@dataclass
class ParameterDistribution:
    """Machine-readable distribution specification for one Netback input."""

    name: str
    method: Literal["historical", "implied", "manual", "expert_prior"]
    distribution_type: str  # "ou", "lognormal", "gbm", "gamma", "beta", "triangular", "normal"
    params: Dict[str, float]
    horizon_days: int
    override: Optional[Dict[str, float]] = field(default_factory=dict)
    source_label: str = ""  # "live", "config_fallback", or "" if N/A

    # bookkeeping
    _base_params: Dict[str, float] = field(default_factory=dict, repr=False)

    def apply_override(self, overrides: Dict[str, float]) -> None:
        """
        Merge trader overrides into params.  Original values are kept in
        ``_base_params`` so the audit trail is preserved.
        """
        if not overrides:
            return
        self._base_params = dict(self.params)
        self.params.update(overrides)
        self.override = dict(overrides)

    @property
    def overridden_keys(self) -> List[str]:
        return list(self.override.keys()) if self.override else []


# ── OU horizon projection ───────────────────────────────────────────

def ou_horizon_distribution(
    s0: float, kappa: float, theta: float, sigma: float, T: int,
) -> Dict[str, float]:
    """
    Exact OU transition distribution at horizon T (days).

        E[X_T]   = theta + (S0 - theta) * exp(-kappa * T)
        Var[X_T] = sigma^2 / (2*kappa) * (1 - exp(-2*kappa*T))
    """
    e_kt = math.exp(-kappa * T)
    mean_T = theta + (s0 - theta) * e_kt
    var_T = (sigma ** 2) / (2 * kappa) * (1 - math.exp(-2 * kappa * T))
    std_T = math.sqrt(max(var_T, 0))
    return {"mean_T": mean_T, "std_T": std_T, "p05": mean_T - 1.645 * std_T, "p95": mean_T + 1.645 * std_T}


# ── GBM / lognormal horizon projection ─────────────────────────────

def gbm_horizon_distribution(
    s0: float, mu_daily: float, sigma_daily: float, T: int,
) -> Dict[str, float]:
    """
    GBM terminal distribution: log(S_T/S0) ~ N((mu-0.5*sig^2)*T, sig^2*T)
    """
    drift = (mu_daily - 0.5 * sigma_daily ** 2) * T
    vol = sigma_daily * math.sqrt(T)
    log_mean = math.log(s0) + drift
    mean_T = math.exp(log_mean + 0.5 * vol ** 2)
    median_T = math.exp(log_mean)
    p05 = math.exp(log_mean - 1.645 * vol)
    p95 = math.exp(log_mean + 1.645 * vol)
    return {"mean_T": mean_T, "median_T": median_T, "sigma_T": vol, "p05": p05, "p95": p95}


# ── triangular / PERT from expert min/mode/max ─────────────────────

def triangular_params(low: float, mode: float, high: float) -> Dict[str, float]:
    mean = (low + mode + high) / 3
    return {"low": low, "mode": mode, "high": high, "mean": mean}


def pert_params(low: float, mode: float, high: float, lambd: float = 4.0) -> Dict[str, float]:
    """Modified PERT: mean = (low + lambd*mode + high) / (lambd + 2)."""
    mean = (low + lambd * mode + high) / (lambd + 2)
    return {"low": low, "mode": mode, "high": high, "lambda": lambd, "mean": mean}


# ── per-parameter estimation functions ──────────────────────────────

def _estimate_price(
    series: pd.Series,
    name: str,
    horizon: int,
) -> ParameterDistribution:
    ou = _estimate_ou_params(series)
    proj = ou_horizon_distribution(ou["s0"], ou["kappa"], ou["theta"], ou["sigma"], horizon)

    gbm = _estimate_gbm_params(series)
    gbm_proj = gbm_horizon_distribution(gbm["s0"], gbm["mu_daily"], gbm["sigma_daily"], horizon)

    params = {
        "s0": ou["s0"],
        "kappa": ou["kappa"],
        "theta": ou["theta"],
        "sigma": ou["sigma"],
        "horizon_mean": proj["mean_T"],
        "horizon_std": proj["std_T"],
        "horizon_p05": proj["p05"],
        "horizon_p95": proj["p95"],
        "gbm_mu_daily": gbm["mu_daily"],
        "gbm_sigma_daily": gbm["sigma_daily"],
        "gbm_horizon_p05": gbm_proj["p05"],
        "gbm_horizon_p95": gbm_proj["p95"],
    }
    return ParameterDistribution(
        name=name,
        method="historical",
        distribution_type="ou",
        params=params,
        horizon_days=horizon,
    )


def _estimate_charter(
    current_rate: float | None,
    horizon: int,
) -> ParameterDistribution:
    s0 = float(current_rate if current_rate is not None else config.DEFAULT_CHARTER_RATE)

    if s0 <= 70_000:
        sigma_ln = 0.35
    elif s0 <= 100_000:
        sigma_ln = 0.45
    else:
        sigma_ln = 0.60

    mu_ln = math.log(s0) - 0.5 * sigma_ln ** 2
    proj = gbm_horizon_distribution(s0, 0.0, sigma_ln / math.sqrt(252), horizon)

    params = {
        "s0": s0,
        "mu_ln": mu_ln,
        "sigma_ln": sigma_ln,
        "sigma_daily": sigma_ln / math.sqrt(252),
        "horizon_median": proj["median_T"],
        "horizon_p05": proj["p05"],
        "horizon_p95": proj["p95"],
    }
    return ParameterDistribution(
        name="Charter_Rate",
        method="expert_prior",
        distribution_type="lognormal",
        params=params,
        horizon_days=horizon,
        source_label="live" if current_rate is not None else "config_fallback",
    )


def _estimate_fuel(
    current_fuel: float | None,
    horizon: int,
) -> ParameterDistribution:
    s0 = float(current_fuel if current_fuel is not None else config.DEFAULT_FUEL_COST_PER_DAY)
    sigma_ln = 0.30
    mu_ln = math.log(s0) - 0.5 * sigma_ln ** 2
    proj = gbm_horizon_distribution(s0, 0.0, sigma_ln / math.sqrt(252), horizon)

    params = {
        "s0": s0,
        "mu_ln": mu_ln,
        "sigma_ln": sigma_ln,
        "sigma_daily": sigma_ln / math.sqrt(252),
        "horizon_median": proj["median_T"],
        "horizon_p05": proj["p05"],
        "horizon_p95": proj["p95"],
    }
    return ParameterDistribution(
        name="Fuel_Cost",
        method="expert_prior",
        distribution_type="lognormal",
        params=params,
        horizon_days=horizon,
        source_label="live" if current_fuel is not None else "config_fallback",
    )


def _estimate_voyage_delay(horizon: int) -> ParameterDistribution:
    month = datetime.now().month
    panama_shift = 3.0 if month in (1, 2, 3, 4) else 0.0
    k, theta_g = 2.0, 1.5
    mean_delay = k * theta_g + panama_shift
    params = {
        "gamma_k": k,
        "gamma_theta": theta_g,
        "panama_shift": panama_shift,
        "mean_delay": mean_delay,
    }
    return ParameterDistribution(
        name="Voyage_Delay",
        method="expert_prior",
        distribution_type="gamma",
        params=params,
        horizon_days=horizon,
    )


def _estimate_bog(horizon: int) -> ParameterDistribution:
    low, high = 0.0008, 0.0015
    mode = float(np.clip(config.BOIL_OFF_RATE, low + 1e-6, high - 1e-6))
    params = triangular_params(low, mode, high)
    return ParameterDistribution(
        name="BOG_Rate",
        method="manual",
        distribution_type="triangular",
        params=params,
        horizon_days=horizon,
    )


def _estimate_fx(
    series: pd.Series,
    horizon: int,
) -> ParameterDistribution:
    gbm = _estimate_gbm_params(series)
    proj = gbm_horizon_distribution(gbm["s0"], gbm["mu_daily"], gbm["sigma_daily"], horizon)

    ann_vol = gbm["sigma_daily"] * math.sqrt(252) if not math.isnan(gbm["sigma_daily"]) else math.nan
    params = {
        "s0": gbm["s0"],
        "mu_daily": gbm["mu_daily"],
        "sigma_daily": gbm["sigma_daily"],
        "annualized_vol": ann_vol,
        "horizon_mean": proj["mean_T"],
        "horizon_p05": proj["p05"],
        "horizon_p95": proj["p95"],
    }
    return ParameterDistribution(
        name="USD_JPY",
        method="historical",
        distribution_type="gbm",
        params=params,
        horizon_days=horizon,
    )


# ── public entry point ──────────────────────────────────────────────

def build_step3_parameter_estimates(
    market_data: pd.DataFrame,
    output_dir: str = config.OUTPUT_DIR,
    horizon_days: int = 45,
    current_charter_rate: float | None = None,
    current_fuel_cost: float | None = None,
    overrides: Dict[str, Dict[str, float]] | None = None,
) -> Dict[str, Any]:
    """
    Build machine-readable parameter estimates for all modeled inputs.

    Parameters
    ----------
    market_data : DataFrame
        Historical prices with columns HH_Price, TTF_Price, JKM_Price, USD_JPY.
    horizon_days : int
        Single target horizon in trading days (default 45 ≈ ~2 months).
    current_charter_rate / current_fuel_cost : float or None
        Live market quotes; config constants as fallback.
    overrides : dict or None
        Keyed by parameter name, e.g.
        ``{"HH_Price": {"sigma": 0.50}, "Charter_Rate": {"s0": 85000}}``
        Each sub-dict is merged into that parameter's ``params``.

    Returns
    -------
    dict  with keys:
        estimates : list[ParameterDistribution]
        summary_df : pd.DataFrame
        csv_path, json_path, md_path : str
    """
    overrides = overrides or {}

    estimates: List[ParameterDistribution] = [
        _estimate_price(market_data["HH_Price"], "HH_Price", horizon_days),
        _estimate_price(market_data["TTF_Price"], "TTF_Price", horizon_days),
        _estimate_price(market_data["JKM_Price"], "JKM_Price", horizon_days),
        _estimate_charter(current_charter_rate, horizon_days),
        _estimate_fx(market_data["USD_JPY"], horizon_days),
        _estimate_fuel(current_fuel_cost, horizon_days),
        _estimate_voyage_delay(horizon_days),
        _estimate_bog(horizon_days),
    ]

    for est in estimates:
        if est.name in overrides:
            est.apply_override(overrides[est.name])

    # ── build summary table ──
    rows = []
    for e in estimates:
        row = {
            "name": e.name,
            "method": e.method,
            "source_label": e.source_label or "-",
            "distribution_type": e.distribution_type,
            "horizon_days": e.horizon_days,
            "overridden": ", ".join(e.overridden_keys) if e.overridden_keys else "-",
        }
        for k, v in e.params.items():
            row[k] = v
        rows.append(row)
    summary_df = pd.DataFrame(rows)

    # ── persist ──
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "step3_parameter_estimates.csv")
    json_path = os.path.join(output_dir, "step3_parameter_estimates.json")
    md_path = os.path.join(output_dir, "step3_parameter_estimates.md")

    summary_df.to_csv(csv_path, index=False)

    json_payload = [asdict(e) for e in estimates]
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_payload, f, indent=2, default=str)

    _write_markdown_report(estimates, md_path)

    return {
        "estimates": estimates,
        "summary_df": summary_df,
        "csv_path": csv_path,
        "json_path": json_path,
        "md_path": md_path,
    }


# ── markdown report ─────────────────────────────────────────────────

def _write_markdown_report(estimates: List[ParameterDistribution], path: str) -> None:
    lines = [
        "# Step 3 - Parameter Estimates (Auto Generated)",
        "",
        "Horizon shown is in *trading days* from today.",
        "",
    ]
    for e in estimates:
        lines.append(f"## {e.name}")
        lines.append(f"- Method: **{e.method}**")
        lines.append(f"- Distribution: `{e.distribution_type}`")
        lines.append(f"- Horizon: {e.horizon_days} days")
        if e.source_label:
            lines.append(f"- Source: `{e.source_label}`")
        if e.overridden_keys:
            lines.append(f"- **Overridden keys**: {', '.join(e.overridden_keys)}")
        lines.append("")
        lines.append("| Parameter | Value |")
        lines.append("| --- | --- |")
        for k, v in e.params.items():
            if isinstance(v, float):
                lines.append(f"| {k} | {v:.6f} |")
            else:
                lines.append(f"| {k} | {v} |")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
