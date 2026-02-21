"""
correlation_structure.py - Step 4 correlation modeling
=====================================================
Estimates the joint dependence structure among Netback risk factors
and provides a Gaussian-Copula sampler for correlated scenario
generation.

Why this matters
----------------
Independent sampling would create impossible scenarios like
"JKM spikes + freight crashes" — in reality JKM up → ship demand up
→ freight up.  Ignoring correlation over-estimates upside probability
and under-estimates tail risk.

Pipeline
--------
1. Estimate historical correlation matrix from daily log-returns.
2. Ensure positive-semi-definiteness (nearest-PSD fix if needed).
3. Cholesky-decompose for fast sampling.
4. Gaussian Copula: correlated N(0,1) → Uniform(0,1) via Phi → feed
   into each marginal's inverse-CDF in Step 5 (Monte Carlo).
5. Allow trader override of individual rho entries.
"""

from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from . import config


# ── ordered factor names used throughout ────────────────────────────

CORE_FACTORS = ["HH_Price", "JKM_Price", "TTF_Price"]
EXTENDED_FACTORS = ["HH_Price", "JKM_Price", "TTF_Price", "Charter_Rate", "USD_JPY", "Fuel_Cost"]

# Charter_Rate and USD_JPY aren't in the daily market_data with those
# exact column names, so we map logical names → DataFrame columns.
_COL_MAP = {
    "HH_Price": "HH_Price",
    "JKM_Price": "JKM_Price",
    "TTF_Price": "TTF_Price",
    "USD_JPY": "USD_JPY",
}


# ── nearest PSD projection ─────────────────────────────────────────

def nearest_psd(mat: np.ndarray, eps: float = 1e-8) -> np.ndarray:
    """
    Project a symmetric matrix onto the positive-semi-definite cone
    using the Higham (2002) alternating-projection algorithm (simplified
    single-pass eigenvalue clipping for speed).
    """
    sym = (mat + mat.T) / 2
    eigvals, eigvecs = np.linalg.eigh(sym)
    eigvals = np.maximum(eigvals, eps)
    psd = eigvecs @ np.diag(eigvals) @ eigvecs.T
    # re-normalize to correlation matrix (diag == 1)
    d = np.sqrt(np.diag(psd))
    psd = psd / np.outer(d, d)
    np.fill_diagonal(psd, 1.0)
    return psd


# ── historical correlation estimation ──────────────────────────────

def estimate_log_return_correlation(
    market_data: pd.DataFrame,
    factors: List[str] | None = None,
    min_obs: int = 30,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Estimate Pearson correlation on daily log-returns.

    Parameters
    ----------
    market_data : DataFrame
        Must contain columns listed in ``factors`` (via _COL_MAP).
    factors : list[str] or None
        Logical factor names.  Defaults to the 4 available in
        market_data (prices + FX).
    min_obs : int
        Minimum overlapping observations required.

    Returns
    -------
    (corr_matrix, log_returns) : tuple of DataFrames
        corr_matrix is N×N with factor names as index/columns.
        log_returns is the cleaned daily log-return DataFrame.
    """
    if factors is None:
        factors = [f for f in EXTENDED_FACTORS if _COL_MAP.get(f, f) in market_data.columns]

    cols = [_COL_MAP.get(f, f) for f in factors]
    sub = market_data[cols].copy()
    sub.columns = factors

    # daily log-returns
    lr = np.log(sub / sub.shift(1)).dropna()

    if len(lr) < min_obs:
        raise ValueError(
            f"Only {len(lr)} overlapping observations for correlation "
            f"estimation (need >= {min_obs})."
        )

    corr = lr.corr()
    return corr, lr


def include_charter_proxy(
    corr_matrix: pd.DataFrame,
    log_returns: pd.DataFrame,
    charter_corr_overrides: Dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Charter rate has no daily time series in market_data.  We inject it
    using domain-knowledge priors (or trader overrides) and expand the
    correlation matrix to include "Charter_Rate".

    Default priors (from industry research):
        Charter ~ JKM  0.55
        Charter ~ TTF  0.40
        Charter ~ HH   0.20
        Charter ~ FX  0.05
    """
    priors = {
        "HH_Price": 0.20,
        "JKM_Price": 0.55,
        "TTF_Price": 0.40,
        "USD_JPY": 0.05,
    }
    if charter_corr_overrides:
        priors.update(charter_corr_overrides)

    factors = list(corr_matrix.columns)
    if "Charter_Rate" in factors:
        return corr_matrix

    new_factors = factors + ["Charter_Rate"]
    n = len(new_factors)
    mat = np.eye(n)

    # copy existing block
    old_n = len(factors)
    mat[:old_n, :old_n] = corr_matrix.values

    # fill charter row/col
    idx_charter = n - 1
    for i, f in enumerate(factors):
        rho = priors.get(f, 0.0)
        mat[i, idx_charter] = rho
        mat[idx_charter, i] = rho

    # ensure PSD after injection
    mat = nearest_psd(mat)

    return pd.DataFrame(mat, index=new_factors, columns=new_factors)


def include_fuel_proxy(
    corr_matrix: pd.DataFrame,
    fuel_corr_overrides: Dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    Fuel cost (for MEGI / X-DF LNG-fuelled vessels) has no daily time
    series.  Inject domain-knowledge prior correlations, similar to the
    Charter_Rate treatment.

    Default priors:
        Fuel ~ HH   0.75   (LNG is the fuel — direct input cost)
        Fuel ~ JKM  0.70
        Fuel ~ TTF  0.60
        Fuel ~ Charter  0.25
        Fuel ~ FX   0.10
    """
    priors = {
        "HH_Price": 0.75,
        "JKM_Price": 0.70,
        "TTF_Price": 0.60,
        "Charter_Rate": 0.25,
        "USD_JPY": 0.10,
    }
    if fuel_corr_overrides:
        priors.update(fuel_corr_overrides)

    factors = list(corr_matrix.columns)
    if "Fuel_Cost" in factors:
        return corr_matrix

    new_factors = factors + ["Fuel_Cost"]
    n = len(new_factors)
    mat = np.eye(n)

    old_n = len(factors)
    mat[:old_n, :old_n] = corr_matrix.values

    idx_fuel = n - 1
    for i, f in enumerate(factors):
        rho = priors.get(f, 0.0)
        mat[i, idx_fuel] = rho
        mat[idx_fuel, i] = rho

    mat = nearest_psd(mat)
    return pd.DataFrame(mat, index=new_factors, columns=new_factors)


# ── Cholesky decomposition ─────────────────────────────────────────

def cholesky_decompose(corr_matrix: pd.DataFrame) -> np.ndarray:
    """
    Lower-triangular Cholesky factor L such that L @ L.T = corr_matrix.
    """
    mat = corr_matrix.values.copy()
    mat = nearest_psd(mat)
    return np.linalg.cholesky(mat)


# ── Gaussian Copula sampler ────────────────────────────────────────

def sample_correlated_uniforms(
    cholesky_L: np.ndarray,
    n_samples: int,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Draw ``n_samples`` rows of correlated Uniform(0,1) via Gaussian
    Copula.

    Returns shape (n_samples, n_factors).
    """
    rng = rng or np.random.default_rng()
    n_factors = cholesky_L.shape[0]
    z_indep = rng.standard_normal((n_samples, n_factors))
    z_corr = z_indep @ cholesky_L.T            # correlated N(0,1)
    u = sp_stats.norm.cdf(z_corr)              # → Uniform(0,1)
    return u


# ── override helpers ───────────────────────────────────────────────

def apply_correlation_overrides(
    corr_matrix: pd.DataFrame,
    overrides: Dict[Tuple[str, str], float] | None = None,
) -> pd.DataFrame:
    """
    Manually override specific pairwise correlations.

    Parameters
    ----------
    overrides : dict
        Keys are (factor_a, factor_b) tuples, values are rho floats.
        Example: ``{("JKM_Price", "Charter_Rate"): 0.70}``
    """
    if not overrides:
        return corr_matrix

    mat = corr_matrix.values.copy()
    factors = list(corr_matrix.columns)
    idx = {f: i for i, f in enumerate(factors)}

    for (fa, fb), rho in overrides.items():
        if fa in idx and fb in idx:
            i, j = idx[fa], idx[fb]
            mat[i, j] = rho
            mat[j, i] = rho

    mat = nearest_psd(mat)
    return pd.DataFrame(mat, index=factors, columns=factors)


# ── public entry point ──────────────────────────────────────────────

def build_step4_correlation_structure(
    market_data: pd.DataFrame,
    output_dir: str = config.OUTPUT_DIR,
    n_demo_samples: int = 5_000,
    charter_corr_overrides: Dict[str, float] | None = None,
    fuel_corr_overrides: Dict[str, float] | None = None,
    pairwise_overrides: Dict[Tuple[str, str], float] | None = None,
) -> Dict[str, Any]:
    """
    Full Step 4 pipeline.

    Returns
    -------
    dict with keys:
        corr_matrix       – pd.DataFrame (full factor set)
        cholesky_L        – np.ndarray
        demo_uniforms     – np.ndarray (n_demo_samples × n_factors)
        factor_names      – list[str]
        csv_path, json_path, md_path – str
    """
    # 1) raw correlation from available series
    raw_corr, log_returns = estimate_log_return_correlation(market_data)

    # 2) expand to include Charter_Rate (proxy / prior)
    full_corr = include_charter_proxy(
        raw_corr, log_returns,
        charter_corr_overrides=charter_corr_overrides,
    )

    # 3) expand to include Fuel_Cost (proxy / prior for MEGI/X-DF)
    full_corr = include_fuel_proxy(
        full_corr,
        fuel_corr_overrides=fuel_corr_overrides,
    )

    # 4) apply any pairwise overrides
    full_corr = apply_correlation_overrides(full_corr, pairwise_overrides)

    # 5) Cholesky
    L = cholesky_decompose(full_corr)

    # 6) demo sample (used later in Step 5 MC and for diagnostics)
    rng = np.random.default_rng(seed=2026)
    demo_u = sample_correlated_uniforms(L, n_demo_samples, rng=rng)

    # 7) empirical correlation of demo sample (sanity check)
    demo_z = sp_stats.norm.ppf(np.clip(demo_u, 1e-10, 1 - 1e-10))
    demo_corr = np.corrcoef(demo_z, rowvar=False)

    factor_names = list(full_corr.columns)

    # ── persist ──
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "step4_correlation_matrix.csv")
    json_path = os.path.join(output_dir, "step4_correlation_structure.json")
    md_path = os.path.join(output_dir, "step4_correlation_structure.md")

    full_corr.to_csv(csv_path)

    payload = {
        "factor_names": factor_names,
        "correlation_matrix": full_corr.values.tolist(),
        "cholesky_L": L.tolist(),
        "n_demo_samples": n_demo_samples,
        "demo_sample_corr": demo_corr.tolist(),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    _write_markdown_report(
        full_corr, demo_corr, factor_names, log_returns, md_path,
    )

    return {
        "corr_matrix": full_corr,
        "cholesky_L": L,
        "demo_uniforms": demo_u,
        "factor_names": factor_names,
        "log_returns": log_returns,
        "csv_path": csv_path,
        "json_path": json_path,
        "md_path": md_path,
    }


# ── markdown report ─────────────────────────────────────────────────

def _fmt(v: float) -> str:
    return f"{v:+.3f}"


def _write_markdown_report(
    corr: pd.DataFrame,
    demo_corr: np.ndarray,
    factors: List[str],
    log_returns: pd.DataFrame,
    path: str,
) -> None:
    lines = [
        "# Step 4 - Correlation Structure (Auto Generated)",
        "",
        f"Estimated from {len(log_returns)} daily log-return observations.",
        "",
        "## Target Correlation Matrix",
        "",
    ]
    # header
    lines.append("| | " + " | ".join(factors) + " |")
    lines.append("| --- | " + " | ".join(["---"] * len(factors)) + " |")
    for i, fi in enumerate(factors):
        vals = " | ".join(_fmt(corr.values[i, j]) for j in range(len(factors)))
        lines.append(f"| **{fi}** | {vals} |")

    lines.extend([
        "",
        "## Gaussian Copula Demo Sample Correlation (sanity check)",
        "",
    ])
    lines.append("| | " + " | ".join(factors) + " |")
    lines.append("| --- | " + " | ".join(["---"] * len(factors)) + " |")
    for i, fi in enumerate(factors):
        vals = " | ".join(_fmt(demo_corr[i, j]) for j in range(len(factors)))
        lines.append(f"| **{fi}** | {vals} |")

    lines.extend([
        "",
        "## Notes",
        "",
        "- **JKM is synthetic** (TTF + Asia premium + noise in current data loader); the JKM–TTF correlation is artificially elevated (~0.95+). With a real JKM feed (e.g. Platts JKM) expect ρ ≈ 0.80–0.85. Until then, consider overriding this pair via `pairwise_overrides`.",
        "- Charter_Rate has no daily series; correlations are injected from domain priors (JKM~0.55, TTF~0.40, HH~0.20, FX~0.05) and can be overridden.",
        "- Fuel_Cost has no daily series; correlations are injected from domain priors for MEGI/X-DF LNG-fuelled vessels (HH~0.75, JKM~0.70, TTF~0.60, Charter~0.25, FX~0.10) and can be overridden.",
        "- Matrix is projected to nearest PSD after any override to guarantee valid Cholesky decomposition.",
        "- Demo sample correlation should closely match target; deviations shrink with more samples.",
        "",
    ])

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
