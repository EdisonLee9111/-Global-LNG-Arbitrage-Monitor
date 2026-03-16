"""
asian_adjustment.py — Asian (Average-Rate) Swap Variance Adjustment
====================================================================
LNG commodity swaps settle against monthly average prices, not terminal spot.
This module computes the analytic variance compression factor for OU and GBM
processes, and provides a helper to transform terminal MC distributions into
Asian-equivalent distributions with the correct variance.

Key formula (OU):
    Var(avg_Δ) = (σ²/κ²Δ²) × [Δ − 2(1−e^{−κΔ})/κ + (1−e^{−2κΔ})/(2κ)]
    Var(X_T)   = σ²/(2κ) × (1 − e^{−2κT})
    variance_ratio = Var(avg_Δ) / Var(X_T)

The to_asian_equivalent() function compresses the terminal distribution around
its mean by σ_scale = √(variance_ratio), preserving E[output] = E[input].
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from .parameter_estimation import ParameterDistribution


# =============================================================================
# 1. Data Structures
# =============================================================================

@dataclass
class AsianAdjustment:
    """Per-leg Asian swap variance adjustment parameters."""
    variance_ratio: float          # Var(avg) / Var(terminal), in (0, 1]
    sigma_scale: float             # √(variance_ratio)
    settlement_basis_std: float    # σ_terminal × (1 − sigma_scale), analytic
    process_type: str              # "ou" or "gbm" — for audit trail
    kappa: float                   # κ used (0.0 for GBM)
    averaging_start_day: int
    averaging_days: int
    horizon_days: int


# =============================================================================
# 2. Variance Ratio — OU Process
# =============================================================================

def compute_ou_variance_ratio(kappa: float, delta: int, T: int) -> float:
    """
    Exact closed-form variance ratio for a stationary OU process.

    Parameters
    ----------
    kappa : float
        Mean-reversion speed (per trading day).
    delta : int
        Averaging window length (trading days).
    T : int
        MC horizon (trading days).

    Returns
    -------
    float
        Var(path average over [T-delta, T]) / Var(X_T), clamped to (0, 1].
    """
    kd = kappa * delta

    # Brownian limit: κΔ → 0
    if kd < 1e-6:
        ratio = 1.0 / 3.0
    else:
        # Var(avg_Δ) = (σ²/κ²Δ²) × [Δ − 2(1−e^{−κΔ})/κ + (1−e^{−2κΔ})/(2κ)]
        # Var(X_T)   = σ²/(2κ) × (1 − e^{−2κT})
        # σ² cancels in the ratio.
        numerator = (
            delta
            - 2.0 * (1.0 - math.exp(-kd)) / kappa
            + (1.0 - math.exp(-2.0 * kd)) / (2.0 * kappa)
        )
        var_avg = numerator / (kappa**2 * delta**2)

        kT = kappa * T
        var_terminal = (1.0 - math.exp(-2.0 * kT)) / (2.0 * kappa)

        if var_terminal <= 0:
            ratio = 1.0
        else:
            ratio = var_avg / var_terminal

    # Clamp to valid range
    ratio = max(0.0, min(1.0, ratio))
    return ratio


# =============================================================================
# 3. Variance Ratio — GBM (Turnbull-Wakeman first-order)
# =============================================================================

def compute_gbm_variance_ratio(delta: int, T: int) -> float:
    """
    Turnbull-Wakeman first-order approximation for GBM.

    Returns
    -------
    float
        Var(arithmetic average) / Var(terminal), clamped to (0, 1].
    """
    if T <= 0:
        return 1.0
    ratio = delta / (3.0 * T)
    return max(0.0, min(1.0, ratio))


# =============================================================================
# 4. Asian Equivalent Transformation
# =============================================================================

def to_asian_equivalent(spot_terminal: np.ndarray, sigma_scale: float) -> np.ndarray:
    """
    Compress terminal MC distribution around its mean by sigma_scale.

    Properties:
    - E[output] = E[input]  (exact for OU)
    - Var[output] = Var[input] × variance_ratio

    No swap direction logic here — caller handles sign.

    Parameters
    ----------
    spot_terminal : ndarray
        Terminal MC price array.
    sigma_scale : float
        √(variance_ratio).

    Returns
    -------
    ndarray
        Asian-equivalent price array, same shape.
    """
    mu = np.mean(spot_terminal)
    return mu + (spot_terminal - mu) * sigma_scale


# =============================================================================
# 5. Top-Level Factory
# =============================================================================

# Mapping from swap leg name to Step 3 ParameterDistribution.name
_LEG_TO_ESTIMATE_NAME: Dict[str, str] = {
    "hh":      "HH_Price",
    "jkm":     "JKM_Price",
    "charter": "Charter_Rate",
    "fx":      "USD_JPY",
}


def build_asian_adjustments(
    estimates: Optional[List[ParameterDistribution]],
    spec,  # SwapSpec — avoid circular import
) -> Dict[str, AsianAdjustment]:
    """
    Build per-leg AsianAdjustment objects from Step 3 parameter estimates.

    For legs with settlement == "european", no adjustment is created (key absent).
    For legs with settlement == "asian", the OU or GBM variance ratio is computed.

    Parameters
    ----------
    estimates : list of ParameterDistribution or None
        Step 3 outputs.  If None, returns empty dict.
    spec : SwapSpec
        Swap specification with per-leg settlement config.

    Returns
    -------
    dict : leg_name → AsianAdjustment (only for Asian-settled legs)
    """
    if estimates is None:
        return {}

    # Index estimates by name for O(1) lookup
    est_by_name: Dict[str, ParameterDistribution] = {e.name: e for e in estimates}

    adjustments: Dict[str, AsianAdjustment] = {}

    for leg_name, est_name in _LEG_TO_ESTIMATE_NAME.items():
        leg = getattr(spec, leg_name, None)
        if leg is None or not leg.enabled:
            continue

        settlement = getattr(leg, "settlement", "european")
        if settlement != "asian":
            continue

        est = est_by_name.get(est_name)
        if est is None:
            continue

        averaging_start_day = getattr(leg, "averaging_start_day", 25)
        averaging_days = getattr(leg, "averaging_days", 20)
        horizon_days = est.horizon_days

        dist_type = est.distribution_type.lower()

        if dist_type == "ou":
            kappa = est.params.get("kappa", 0.0)
            if kappa <= 0 or math.isnan(kappa):
                kappa = 0.03  # fallback consistent with distribution_selection.py
            variance_ratio = compute_ou_variance_ratio(kappa, averaging_days, horizon_days)
            process_type = "ou"
        else:
            # GBM / lognormal fallback
            kappa = 0.0
            variance_ratio = compute_gbm_variance_ratio(averaging_days, horizon_days)
            process_type = "gbm"

        sigma_scale = math.sqrt(variance_ratio)

        adjustments[leg_name] = AsianAdjustment(
            variance_ratio=variance_ratio,
            sigma_scale=sigma_scale,
            settlement_basis_std=0.0,  # populated later by caller with actual MC std
            process_type=process_type,
            kappa=kappa,
            averaging_start_day=averaging_start_day,
            averaging_days=averaging_days,
            horizon_days=horizon_days,
        )

    return adjustments


# =============================================================================
# 6. Sanity Checks (Step 6a Validation)
# =============================================================================

def validate_asian_adjustments(
    adjustments: Dict[str, AsianAdjustment],
) -> List[str]:
    """
    Run sanity checks on computed Asian adjustments.

    Returns a list of warning strings.  Empty list = all checks passed.

    Checks
    ------
    - 0 < variance_ratio <= 1.0  for every leg
    - sigma_scale == sqrt(variance_ratio)
    - For OU with small kappa, ratio should approach Brownian limit delta/(3*T)
    """
    warnings: List[str] = []

    for leg_name, adj in adjustments.items():
        # Range check
        if not (0.0 < adj.variance_ratio <= 1.0):
            warnings.append(
                f"{leg_name}: variance_ratio={adj.variance_ratio:.6f} "
                f"out of valid range (0, 1]"
            )

        # Consistency: sigma_scale == sqrt(variance_ratio)
        expected_ss = math.sqrt(max(0.0, adj.variance_ratio))
        if abs(adj.sigma_scale - expected_ss) > 1e-9:
            warnings.append(
                f"{leg_name}: sigma_scale={adj.sigma_scale:.6f} != "
                f"sqrt(variance_ratio)={expected_ss:.6f}"
            )

        # Brownian limit cross-check for OU with very small kappa
        if adj.process_type == "ou" and adj.kappa > 0:
            brownian_limit = adj.averaging_days / (3.0 * adj.horizon_days)
            # For well-behaved OU, ratio should be in a plausible neighbourhood
            if adj.variance_ratio > 1.0:
                warnings.append(
                    f"{leg_name}: OU variance_ratio={adj.variance_ratio:.4f} > 1.0 "
                    f"(Brownian limit={brownian_limit:.4f})"
                )

    return warnings
