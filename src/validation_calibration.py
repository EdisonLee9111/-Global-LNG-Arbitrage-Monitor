"""
validation_calibration.py - Step 5 distribution validation & calibration
========================================================================
After Steps 1-4 set up marginal distributions and their joint structure,
this module answers: "Do the numbers make sense?"

Three validation layers
-----------------------
A. Range check       – P1/P99 must fall within physical bounds.
B. Historical coverage – the 90% CI should cover ~90% of actual data.
C. Extreme scenario audit – surface the 5 most extreme draws for
                            human (trader) review.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)

from . import config
from .parameter_estimation import (
    ParameterDistribution,
    ou_horizon_distribution,
    gbm_horizon_distribution,
)
from .correlation_structure import sample_correlated_uniforms


# ── physical bounds (domain knowledge) ──────────────────────────────

PHYSICAL_BOUNDS: Dict[str, Tuple[float, float]] = {
    "HH_Price":     (0.50, 50.0),
    "TTF_Price":    (1.0,  80.0),
    "JKM_Price":    (1.0,  100.0),
    "Charter_Rate": (10_000, 500_000),
    "USD_JPY":      (80.0, 250.0),
    "Fuel_Cost":    (3_000, 100_000),
    "Voyage_Delay": (0.0,  30.0),
    "BOG_Rate":     (0.0005, 0.0020),
}


# ── marginal inverse-CDF (Uniform → physical value) ────────────────

def _inv_cdf_ou(u: np.ndarray, p: Dict[str, float], T: int) -> np.ndarray:
    """Map U(0,1) → OU horizon value via normal inverse-CDF.

    A positive floor is enforced because the standard OU is Gaussian and
    can produce negative draws when mean_T is low relative to std_T.
    Energy prices are strictly positive, and downstream code (e.g. log
    transforms) relies on this.
    """
    proj = ou_horizon_distribution(p["s0"], p["kappa"], p["theta"], p["sigma"], T)
    raw = sp_stats.norm.ppf(u, loc=proj["mean_T"], scale=proj["std_T"])
    floor = p.get("price_floor", 1e-4)
    return np.maximum(raw, floor)


def _inv_cdf_lognormal(u: np.ndarray, p: Dict[str, float], T: int) -> np.ndarray:
    sig_daily = p.get("sigma_daily", p.get("gbm_sigma_daily", None))
    if sig_daily is None:
        logger.warning(
            "sigma_daily / gbm_sigma_daily not found in params %s; "
            "falling back to 0.01 — check parameter key names.",
            list(p.keys()),
        )
        sig_daily = 0.01
    mu_daily = p.get("mu_daily", 0.0)
    drift = (mu_daily - 0.5 * sig_daily ** 2) * T
    vol = sig_daily * math.sqrt(T)
    log_mean = math.log(p["s0"]) + drift
    return np.exp(sp_stats.norm.ppf(u, loc=log_mean, scale=max(vol, 1e-10)))


def _inv_cdf_gbm(u: np.ndarray, p: Dict[str, float], T: int) -> np.ndarray:
    return _inv_cdf_lognormal(u, p, T)


def _inv_cdf_gamma(u: np.ndarray, p: Dict[str, float], _T: int) -> np.ndarray:
    k = p["gamma_k"]
    theta = p["gamma_theta"]
    shift = p.get("panama_shift", 0.0)
    return sp_stats.gamma.ppf(u, a=k, scale=theta) + shift


def _inv_cdf_triangular(u: np.ndarray, p: Dict[str, float], _T: int) -> np.ndarray:
    low, mode, high = p["low"], p["mode"], p["high"]
    c = (mode - low) / (high - low)
    return sp_stats.triang.ppf(u, c, loc=low, scale=high - low)


_INV_CDF = {
    "ou": _inv_cdf_ou,
    "lognormal": _inv_cdf_lognormal,
    "gbm": _inv_cdf_gbm,
    "gamma": _inv_cdf_gamma,
    "triangular": _inv_cdf_triangular,
}


# ── correlated MC sample generation ────────────────────────────────

def generate_correlated_scenarios(
    estimates: List[ParameterDistribution],
    cholesky_L: np.ndarray,
    factor_names: List[str],
    n_samples: int = 10_000,
    seed: int = 2026,
) -> pd.DataFrame:
    """
    Draw ``n_samples`` correlated scenarios via Gaussian Copula +
    marginal inverse-CDFs.

    Factors in ``factor_names`` (from Step 4) get correlated uniforms;
    remaining parameters (Voyage_Delay, BOG_Rate) are sampled
    independently.
    """
    rng = np.random.default_rng(seed)

    # correlated uniforms for factors in the copula
    u_corr = sample_correlated_uniforms(cholesky_L, n_samples, rng=rng)
    copula_map = {name: idx for idx, name in enumerate(factor_names)}

    result = {}
    for est in estimates:
        inv_fn = _INV_CDF.get(est.distribution_type)
        if inv_fn is None:
            continue

        if est.name in copula_map:
            u = u_corr[:, copula_map[est.name]]
        else:
            u = rng.uniform(size=n_samples)

        vals = inv_fn(u, est.params, est.horizon_days)
        result[est.name] = vals

    return pd.DataFrame(result)


# ── Validation A: range check ──────────────────────────────────────

@dataclass
class RangeCheckResult:
    parameter: str
    p01: float
    p99: float
    bound_low: float
    bound_high: float
    pct_below_low: float
    pct_above_high: float
    status: str  # "PASS" or "WARN"


def run_range_checks(scenarios: pd.DataFrame) -> List[RangeCheckResult]:
    results = []
    for col in scenarios.columns:
        vals = scenarios[col].dropna()
        if len(vals) == 0:
            continue
        p01, p99 = float(np.percentile(vals, 1)), float(np.percentile(vals, 99))
        lo, hi = PHYSICAL_BOUNDS.get(col, (-np.inf, np.inf))
        pct_below = float((vals < lo).mean() * 100)
        pct_above = float((vals > hi).mean() * 100)
        ok = pct_below < 2.0 and pct_above < 2.0
        results.append(RangeCheckResult(
            parameter=col, p01=p01, p99=p99,
            bound_low=lo, bound_high=hi,
            pct_below_low=pct_below, pct_above_high=pct_above,
            status="PASS" if ok else "WARN",
        ))
    return results


# ── Validation B: historical coverage ──────────────────────────────

@dataclass
class CoverageResult:
    parameter: str
    ci_level: float
    avg_ci_low: float
    avg_ci_high: float
    n_windows: int
    n_hits: int
    coverage_pct: float
    status: str  # "PASS", "TOO_NARROW", "TOO_WIDE"


# Symmetric tolerance band (percentage points) around target CI level.
# e.g. for 90% CI the PASS band is [80%, 100%].
_COVERAGE_TOLERANCE_PP = 10.0


def run_coverage_checks(
    estimates: List[ParameterDistribution],
    market_data: pd.DataFrame,
    ci_level: float = 0.90,
) -> List[CoverageResult]:
    """
    Rolling-backtest coverage check.

    For each historical date *t* with enough forward data, use hist[t] as
    the starting price, compute the T-day-ahead CI, and check whether the
    realised price hist[t+T] falls inside.  The hit-rate should be close
    to ``ci_level``.
    """
    col_map = {
        "HH_Price": "HH_Price",
        "TTF_Price": "TTF_Price",
        "JKM_Price": "JKM_Price",
        "USD_JPY": "USD_JPY",
    }
    alpha = (1 - ci_level) / 2
    z = sp_stats.norm.ppf(1 - alpha)

    results = []
    for est in estimates:
        col = col_map.get(est.name)
        if col is None or col not in market_data.columns:
            continue

        hist = market_data[col].dropna().values
        p = est.params
        T = est.horizon_days

        n_windows = len(hist) - T
        if n_windows < 10:
            continue

        s_starts = hist[:n_windows]
        s_actuals = hist[T: T + n_windows]

        if est.distribution_type == "ou":
            e_kt = math.exp(-p["kappa"] * T)
            var_T = (p["sigma"] ** 2) / (2 * p["kappa"]) * (
                1 - math.exp(-2 * p["kappa"] * T)
            )
            std_T = math.sqrt(max(var_T, 0))

            means = p["theta"] + (s_starts - p["theta"]) * e_kt
            los = means - z * std_T
            his = means + z * std_T

        elif est.distribution_type in ("gbm", "lognormal"):
            sig_d = p.get("sigma_daily", p.get("gbm_sigma_daily", None))
            if sig_d is None:
                logger.warning(
                    "sigma_daily key missing for %s in coverage check; "
                    "falling back to 0.01.",
                    est.name,
                )
                sig_d = 0.01
            mu_d = p.get("mu_daily", 0.0)
            drift = (mu_d - 0.5 * sig_d ** 2) * T
            vol = sig_d * math.sqrt(T)

            log_ms = np.log(s_starts) + drift
            los = np.exp(log_ms + sp_stats.norm.ppf(alpha) * vol)
            his = np.exp(log_ms + sp_stats.norm.ppf(1 - alpha) * vol)
        else:
            continue

        hits = int(((s_actuals >= los) & (s_actuals <= his)).sum())
        cov_pct = hits / n_windows * 100

        target = ci_level * 100
        if cov_pct < target - _COVERAGE_TOLERANCE_PP:
            status = "TOO_NARROW"
        elif cov_pct > target + _COVERAGE_TOLERANCE_PP:
            status = "TOO_WIDE"
        else:
            status = "PASS"

        results.append(CoverageResult(
            parameter=est.name, ci_level=ci_level,
            avg_ci_low=float(los.mean()), avg_ci_high=float(his.mean()),
            n_windows=n_windows, n_hits=hits,
            coverage_pct=cov_pct, status=status,
        ))
    return results


# ── Validation C: extreme scenario audit ───────────────────────────

def extract_extreme_scenarios(
    scenarios: pd.DataFrame,
    n_extreme: int = 5,
) -> Dict[str, pd.DataFrame]:
    """
    For each parameter, return the ``n_extreme`` most extreme
    (highest and lowest) full scenario rows.
    """
    extremes = {}
    for col in scenarios.columns:
        idx_low = scenarios[col].nsmallest(n_extreme).index
        idx_high = scenarios[col].nlargest(n_extreme).index
        combined = scenarios.loc[idx_low.union(idx_high)].copy()
        combined["_extreme_type"] = "low"
        combined.loc[idx_high, "_extreme_type"] = "high"
        combined = combined.sort_values(col)
        extremes[col] = combined
    return extremes


# ── public entry point ──────────────────────────────────────────────

def build_step5_validation(
    estimates: List[ParameterDistribution],
    cholesky_L: np.ndarray,
    factor_names: List[str],
    market_data: pd.DataFrame,
    output_dir: str = config.OUTPUT_DIR,
    n_samples: int = 10_000,
    seed: int = 2026,
) -> Dict[str, Any]:
    """
    Full Step 5 validation & calibration pipeline.
    """
    # 1) generate correlated scenarios
    scenarios = generate_correlated_scenarios(
        estimates, cholesky_L, factor_names,
        n_samples=n_samples, seed=seed,
    )

    # 2) range checks
    range_results = run_range_checks(scenarios)

    # 3) historical coverage
    coverage_results = run_coverage_checks(estimates, market_data)

    # 4) extreme scenarios
    extremes = extract_extreme_scenarios(scenarios, n_extreme=5)

    # ── persist ──
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "step5_validation_scenarios.csv")
    md_path = os.path.join(output_dir, "step5_validation_report.md")

    scenarios.to_csv(csv_path, index=False)
    _write_validation_report(
        range_results, coverage_results, extremes, scenarios, md_path,
    )

    return {
        "scenarios": scenarios,
        "range_checks": range_results,
        "coverage_checks": coverage_results,
        "extremes": extremes,
        "csv_path": csv_path,
        "md_path": md_path,
    }


# ── markdown report ─────────────────────────────────────────────────

def _write_validation_report(
    range_results: List[RangeCheckResult],
    coverage_results: List[CoverageResult],
    extremes: Dict[str, pd.DataFrame],
    scenarios: pd.DataFrame,
    path: str,
) -> None:
    lines = [
        "# Step 5 - Validation & Calibration Report (Auto Generated)",
        "",
        f"Monte Carlo sample size: **{len(scenarios):,}** correlated scenarios.",
        "",
        "---",
        "",
        "## A. Range Check (P1 / P99 vs physical bounds)",
        "",
        "| Parameter | P1 | P99 | Bound Low | Bound High | %<Low | %>High | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in range_results:
        lines.append(
            f"| {r.parameter} | {r.p01:.2f} | {r.p99:.2f} | "
            f"{r.bound_low:,.2f} | {r.bound_high:,.2f} | "
            f"{r.pct_below_low:.2f}% | {r.pct_above_high:.2f}% | "
            f"**{r.status}** |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## B. Historical Coverage — Rolling Backtest",
        "",
        "For each historical date *t*, the model projects a CI from hist[t] "
        "over the estimation horizon T, then checks whether the realised "
        "price hist[t+T] falls inside.",
        "",
        "| Parameter | CI Level | Avg CI Low | Avg CI High | Windows | Hits | Coverage% | Status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for c in coverage_results:
        lines.append(
            f"| {c.parameter} | {c.ci_level:.0%} | {c.avg_ci_low:.2f} | "
            f"{c.avg_ci_high:.2f} | {c.n_windows} | {c.n_hits} | "
            f"{c.coverage_pct:.1f}% | **{c.status}** |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## C. Extreme Scenario Audit (5 lowest + 5 highest per factor)",
        "",
        "Show these to the trading desk. Ask: *\"Could this happen?\"*",
        "",
    ])
    for param, df in extremes.items():
        lines.append(f"### {param}")
        lines.append("")
        cols_to_show = [c for c in df.columns if c != "_extreme_type"]
        header = "| " + " | ".join(cols_to_show) + " | Type |"
        sep = "| " + " | ".join(["---"] * (len(cols_to_show) + 1)) + " |"
        lines.append(header)
        lines.append(sep)
        for _, row in df.iterrows():
            vals = " | ".join(f"{row[c]:.4f}" if isinstance(row[c], float) else str(row[c]) for c in cols_to_show)
            lines.append(f"| {vals} | {row['_extreme_type']} |")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Interpretation Guide",
        "",
        "- **PASS**: distribution is well-calibrated for this check.",
        "- **WARN** (range): >2% of draws fall outside physical bounds — consider tightening tails or adding floor/cap.",
        "- **TOO_NARROW** (coverage): CI covers much less than target — volatility is under-estimated, widen sigma.",
        "- **TOO_WIDE** (coverage): CI covers much more than target — volatility is over-estimated, tighten sigma.",
        "",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
