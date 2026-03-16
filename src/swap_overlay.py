"""
swap_overlay.py — Financial Swap / FFA Overlay for LNG Arbitrage Hedging
=========================================================================
Applies financial swap P&L on top of the physical spread distributions
produced by the Monte Carlo engine.  Zero-invasive: reads MCSpreadOutput
as input, produces HedgedOutput as output without touching any upstream
calculation.

Hedging scope
-------------
HH Price Swap   (Pay Fixed / Receive Float, $/MMBtu):
    Physical position is short HH (higher HH = higher input cost).
    Swap offsets this: receive (HH_spot − HH_fixed) per MMBtu.

JKM Price Swap  (Receive Fixed / Pay Float, $/MMBtu):
    Physical position is long JKM (higher JKM = higher revenue).
    Swap offsets downside: receive (JKM_fixed − JKM_spot) per MMBtu.

Charter FFA     (Pay Fixed / Receive Float, $/day → $/MMBtu):
    Physical position is short Charter_Rate (higher charter = higher cost).
    FFA offsets this: receive (Charter_spot − FFA_fixed) per day.
    Converted to $/MMBtu via scenario-specific rt_days / cargo_size so the
    P&L is expressed in the same unit as the spread before overlay.
    NOTE: cargo_size (not delivered volume) is used as the denominator —
    a 1–3% approximation.  The residual is part of the structural basis risk.

FX Forward      (disabled by default):
    Relevant only for JPY-denominated contracts.  Second-order effect
    for standard USD-settled LNG trades.

Structural basis risk
---------------------
Even at 100% hedge ratio, the JKM swap only covers the JKM component
embedded in Netback, not the full Netback value:
    Netback = JKM × (1 − BOG_ratio) − shipping − canal − liquefaction
So 100% JKM hedge ≈ (1 − mean_BOG) × 100% ≈ 95–98% effective on spread.
The remaining 2–5% is irreducible structural basis risk.  This module
computes and reports that residual explicitly.

Target
------
Optimal Strategy spread / TCE from OptimalStrategyResult (real-option
over route selection).  The swap overlay is applied to the optimal spread
because it represents the cargo the trader actually intends to execute.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from . import config
from .monte_carlo_spread import (
    MCSpreadOutput,
    MCRouteResult,
    OptimalStrategyResult,
    DistributionStats,
    compute_distribution_stats,
)


# =============================================================================
# 1. Input Specification Data Structures
# =============================================================================

@dataclass
class LegSpec:
    """Configuration for a single swap / FFA hedging leg."""
    enabled: bool = False
    hedge_ratio: float = 0.8        # fraction of exposure to hedge, 0.0 – 1.0
    swap_rate: float | None = None  # None → auto-resolve to MC mean (fair value)
    settlement: str = "european"          # "european" | "asian"
    averaging_start_day: int = 25         # first day of averaging window
    averaging_days: int = 20              # number of trading days in window


@dataclass
class SwapSpec:
    """
    Full specification for a swap overlay run.

    Fields
    ------
    mode : "auto" | "manual"
        "auto"   → swap_rate for each enabled leg = mean(MC distribution).
                   This represents the theoretical fair value; implied cost = 0.
        "manual" → trader supplies swap_rate in LegSpec.swap_rate.
                   Difference from MC mean is the implied hedge cost / premium.
    hh, jkm : LegSpec
        Price swaps in $/MMBtu.  Settle against raw HH_Price / JKM_Price.
    charter : LegSpec
        FFA (Freight Forward Agreement) in $/day.
        Settle against Charter_Rate.  P&L converted to $/MMBtu via
        scenario-specific rt_days for the optimal chosen route.
    fx : LegSpec
        USD/JPY FX forward.  Disabled by default; relevant only for
        JPY-denominated contracts (second-order for USD LNG trades).
    notional_mmbtu : float
        Cargo notional (MMBtu).  Defaults to config.STANDARD_CARGO_SIZE_MMBTU.
    basis_noise_std : float
        Optional i.i.d. Gaussian residual to stress-test basis risk.
        Set > 0 to add synthetic noise to total swap P&L.
    """
    mode: str = "auto"
    hh: LegSpec = field(
        default_factory=lambda: LegSpec(enabled=True,  hedge_ratio=0.8)
    )
    jkm: LegSpec = field(
        default_factory=lambda: LegSpec(enabled=True,  hedge_ratio=0.8)
    )
    charter: LegSpec = field(
        default_factory=lambda: LegSpec(enabled=False, hedge_ratio=0.5)
    )
    fx: LegSpec = field(
        default_factory=lambda: LegSpec(enabled=False, hedge_ratio=0.5)
    )
    notional_mmbtu: float = config.STANDARD_CARGO_SIZE_MMBTU
    basis_noise_std: float = 0.0


# =============================================================================
# 2. Output Data Structures
# =============================================================================

@dataclass
class PerLegPnL:
    """P&L attribution statistics for a single swap / FFA leg ($/MMBtu)."""
    leg: str
    enabled: bool
    swap_rate: float
    mc_mean: float
    implied_cost: float   # swap_rate − mc_mean  (+  = overpaid vs fair value)
    hedge_ratio: float
    pnl_mean: float
    pnl_std: float
    pnl_p05: float
    pnl_p95: float


@dataclass
class HedgeEffectiveness:
    """
    Metrics comparing the hedged vs unhedged optimal spread distribution.

    All spread metrics are in $/MMBtu.
    """
    variance_reduction: float     # 1 − Var(hedged)/Var(unhedged), 0 → 1
    var_reduction: float          # VaR_unhedged − VaR_hedged (+ = improvement)
    cvar_reduction: float         # CVaR_unhedged − CVaR_hedged (+ = improvement)
    hedge_cost: float             # E[unhedged] − E[hedged]  (+ = cost of hedging)
    sharpe_unhedged: float        # mean / std for unhedged spread
    sharpe_hedged: float          # mean / std for hedged spread
    sharpe_improvement: float     # sharpe_hedged − sharpe_unhedged
    prob_loss_change: float       # P(hedged<0) − P(unhedged<0)  (− = improvement)
    jkm_effective_coverage: float # fraction of JKM exposure actually hedged
    basis_risk_note: str          # human-readable structural basis risk description
    settlement_basis_std: float = 0.0             # std(spot_T − avg_equivalent), analytic
    asian_variance_ratios: Dict[str, float] = field(default_factory=dict)  # per-leg variance_ratio


@dataclass
class RatioSensitivityRow:
    """Hedge effectiveness metrics at a specific uniform hedge ratio."""
    hedge_ratio: float
    var_5pct: float
    cvar_5pct: float
    variance_reduction: float
    hedge_cost: float
    prob_positive: float


@dataclass
class HedgedOutput:
    """Top-level container for all swap overlay results."""
    swap_spec: SwapSpec
    swap_rates: Dict[str, float]          # actual rates used (auditable)
    hedged_spread: np.ndarray             # N scenarios, $/MMBtu
    hedged_tce: np.ndarray                # N scenarios, $/day
    hedged_stats_spread: DistributionStats
    hedged_stats_tce: DistributionStats
    unhedged_stats_spread: DistributionStats
    unhedged_stats_tce: DistributionStats
    effectiveness: HedgeEffectiveness
    ratio_sensitivity: List[RatioSensitivityRow]
    per_leg_pnl: List[PerLegPnL]


# =============================================================================
# 3. Internal Helper — rt_days for Optimal Chosen Route
# =============================================================================

def _build_rt_days_optimal(
    route_results: List[MCRouteResult],
    chosen_route_idx: np.ndarray,
) -> np.ndarray:
    """
    Build the per-scenario rt_days array aligned to the optimal strategy's
    chosen route.

    For "No-Go" scenarios (chosen_route_idx >= len(route_results)), the FFA
    still settles financially (it is a booked financial contract regardless of
    whether the cargo moves).  We use the mean rt_days across all routes as a
    proxy for the contracted voyage duration.

    Parameters
    ----------
    route_results : list of MCRouteResult
        All computed routes from the MC engine.
    chosen_route_idx : ndarray, shape (N,)
        Per-scenario optimal route index from OptimalStrategyResult.

    Returns
    -------
    rt_days : ndarray, shape (N,)
    """
    n_routes = len(route_results)
    n = len(chosen_route_idx)

    # Stack shape: (n_routes, N)
    rt_stack = np.stack([rr.total_rt_days for rr in route_results], axis=0)
    mean_rt_days = float(np.mean(rt_stack))

    # Clamp no-go indices to [0, n_routes-1], then overwrite with mean
    clamped = np.minimum(chosen_route_idx, n_routes - 1)
    rt_days = rt_stack[clamped, np.arange(n)].copy()

    no_go_mask = chosen_route_idx >= n_routes
    rt_days[no_go_mask] = mean_rt_days

    return rt_days


# =============================================================================
# 4. Step 1 — Resolve Swap Rates
# =============================================================================

def resolve_swap_rates(
    spec: SwapSpec,
    scenarios: pd.DataFrame,
    eff_prices: Optional[Dict[str, np.ndarray]] = None,
) -> Dict[str, float]:
    """
    Determine the effective swap / FFA fixed rate for each leg.

    "auto"   → rate = mean(effective prices)  ≡ theoretical fair value.
               When Asian settlement is active, eff_prices contains the
               variance-compressed arrays so the fair rate is computed on
               those (for OU, E[avg] = E[terminal] so the result is identical;
               for GBM fallback they differ due to Jensen's inequality).
    "manual" → rate = LegSpec.swap_rate (must not be None for enabled legs).

    Disabled legs are included in the output dict (rate = 0.0) for auditability.

    Returns
    -------
    dict : keys "hh", "jkm", "charter", "fx"
    """
    col_map: Dict[str, str] = {
        "hh":      "HH_Price",
        "jkm":     "JKM_Price",
        "charter": "Charter_Rate",
        "fx":      "USD_JPY",
    }

    def _resolve(leg: LegSpec, leg_name: str, col: str) -> float:
        if not leg.enabled:
            return 0.0
        if spec.mode == "auto" or leg.swap_rate is None:
            if eff_prices and leg_name in eff_prices:
                return float(np.mean(eff_prices[leg_name]))
            return float(np.mean(scenarios[col].values))
        return float(leg.swap_rate)

    return {
        name: _resolve(getattr(spec, name), name, col_map[name])
        for name in col_map
    }


# =============================================================================
# 5. Step 2 — Compute Swap P&L (Vectorized)
# =============================================================================

def compute_swap_pnl(
    spec: SwapSpec,
    rates: Dict[str, float],
    scenarios: pd.DataFrame,
    route_results: List[MCRouteResult],
    optimal: OptimalStrategyResult,
    rng: Optional[np.random.Generator] = None,
    eff_prices: Optional[Dict[str, np.ndarray]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute total swap P&L in $/MMBtu for all N scenarios simultaneously.

    Swap mechanics
    --------------
    HH  (Pay Fixed / Receive Float):
        pnl[i] = h_hh × (HH_spot[i] − HH_fixed)
        Trader is short HH physically; swap pays when HH rises.

    JKM (Receive Fixed / Pay Float):
        pnl[i] = h_jkm × (JKM_fixed − JKM_spot[i])
        Trader is long JKM physically; swap pays when JKM falls.

    Charter FFA (Pay Fixed / Receive Float, $/day → $/MMBtu):
        ffa_day[i]   = h_ch × (Charter_spot[i] − FFA_fixed)
        pnl_mmbtu[i] = ffa_day[i] × rt_days_optimal[i] / cargo_size
        Dividing by cargo_size (not delivered volume) introduces a 1–3%
        approximation captured in the structural basis risk note.

    FX (disabled by default):
        P&L = h_fx × (FX_spot[i] − FX_fixed) / FX_fixed
        Expressed as a fraction of notional; impact on spread is second-order.
        Only meaningful for JPY-denominated contracts.

    Parameters
    ----------
    rng : numpy Generator or None
        Passed to the optional basis noise term.  Created internally if None.
    eff_prices : dict or None
        Effective (Asian-adjusted) price arrays keyed by leg name.
        If None, raw scenario columns are used (European behavior).

    Returns
    -------
    total_pnl_spread : ndarray, shape (N,), $/MMBtu
        Additive overlay on optimal_spread.
    rt_days_optimal : ndarray, shape (N,)
        Scenario-specific rt_days for the chosen route (used externally
        to derive hedged_tce from hedged_spread).
    """
    n = len(scenarios)
    _ep = eff_prices or {}
    hh_price     = _ep.get("hh",      scenarios["HH_Price"].values)
    jkm_price    = _ep.get("jkm",     scenarios["JKM_Price"].values)
    charter_rate = _ep.get("charter",  scenarios["Charter_Rate"].values)
    usd_jpy      = _ep.get("fx",      scenarios["USD_JPY"].values)
    cargo_size   = spec.notional_mmbtu

    rt_days = _build_rt_days_optimal(route_results, optimal.chosen_route_idx)

    total_pnl = np.zeros(n, dtype=np.float64)

    if spec.hh.enabled:
        total_pnl += spec.hh.hedge_ratio * (hh_price - rates["hh"])

    if spec.jkm.enabled:
        total_pnl += spec.jkm.hedge_ratio * (rates["jkm"] - jkm_price)

    if spec.charter.enabled:
        ffa_day_pnl = spec.charter.hedge_ratio * (charter_rate - rates["charter"])
        total_pnl += ffa_day_pnl * rt_days / cargo_size

    if spec.fx.enabled:
        # Normalised: express FX move as a fraction of the reference FX rate,
        # then scale to notional.  Rough proxy for JPY-denominated exposure.
        fx_ref = rates["fx"]
        if fx_ref > 0:
            total_pnl += spec.fx.hedge_ratio * (usd_jpy - fx_ref) / fx_ref

    if spec.basis_noise_std > 0:
        _rng = rng if rng is not None else np.random.default_rng(seed=42)
        total_pnl += _rng.normal(0.0, spec.basis_noise_std, n)

    return total_pnl, rt_days


# =============================================================================
# 6. Step 3 — Overlay on Spread and Derive TCE
# =============================================================================

def overlay_on_spread(
    optimal_spread: np.ndarray,
    total_pnl: np.ndarray,
    rt_days: np.ndarray,
    cargo_size: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Produce hedged spread and TCE distributions.

        hedged_spread[i] = optimal_spread[i] + total_pnl[i]    ($/MMBtu)
        hedged_tce[i]    = hedged_spread[i] × cargo_size / rt_days[i]  ($/day)

    The hedged_tce is derived from hedged_spread so the two metrics are
    internally consistent.  All three swap legs are already in $/MMBtu inside
    total_pnl, so a single addition suffices.
    """
    hedged_spread = optimal_spread + total_pnl
    hedged_tce    = hedged_spread * cargo_size / rt_days
    return hedged_spread, hedged_tce


# =============================================================================
# 7. Step 4a — Hedge Effectiveness Metrics
# =============================================================================

def compute_hedge_effectiveness(
    unhedged_spread: np.ndarray,
    hedged_spread: np.ndarray,
    spec: SwapSpec,
    route_results: List[MCRouteResult],
    adjustments: Optional[Dict] = None,
    scenarios: Optional[pd.DataFrame] = None,
) -> HedgeEffectiveness:
    """
    Compute comprehensive effectiveness metrics comparing the two distributions.

    The structural basis risk note is computed from the mean BOG remaining
    ratio across all routes, which determines how much of the JKM exposure in
    Netback is actually covered by a JKM price swap.

    Parameters
    ----------
    adjustments : dict or None
        Per-leg AsianAdjustment objects (from build_asian_adjustments).
    scenarios : DataFrame or None
        Raw MC scenarios, needed to compute settlement_basis_std.
    """
    var_uh  = float(np.var(unhedged_spread, ddof=1))
    var_h   = float(np.var(hedged_spread,   ddof=1))
    std_uh  = float(np.std(unhedged_spread, ddof=1))
    std_h   = float(np.std(hedged_spread,   ddof=1))
    mean_uh = float(np.mean(unhedged_spread))
    mean_h  = float(np.mean(hedged_spread))

    var5_uh = float(np.percentile(unhedged_spread, 5))
    var5_h  = float(np.percentile(hedged_spread,   5))
    tail_uh = unhedged_spread[unhedged_spread <= var5_uh]
    tail_h  = hedged_spread[hedged_spread     <= var5_h]
    cvar_uh = float(np.mean(tail_uh)) if len(tail_uh) > 0 else var5_uh
    cvar_h  = float(np.mean(tail_h))  if len(tail_h)  > 0 else var5_h

    sharpe_uh = mean_uh / std_uh if std_uh > 0 else 0.0
    sharpe_h  = mean_h  / std_h  if std_h  > 0 else 0.0

    # Structural basis risk: JKM swap hedges JKM × (1 − BOG_ratio), not JKM × 1.0
    # Effective coverage = mean(delivered_volume / cargo_size) across all routes
    coverage_per_route = [
        float(np.mean(rr.delivered_volume)) / spec.notional_mmbtu
        for rr in route_results
    ]
    mean_coverage = float(np.mean(coverage_per_route))
    residual_pct  = (1.0 - mean_coverage) * 100.0

    basis_note = (
        f"100% JKM swap covers ≈{mean_coverage * 100:.1f}% of Netback JKM "
        f"exposure (remaining_ratio ≈ {mean_coverage:.3f} after BOG decay). "
        f"The remaining ≈{residual_pct:.1f}% is structural basis risk from "
        f"BOG decay, voyage-time variability, and the non-linear Netback "
        f"structure (shipping + canal fees dilute the JKM coefficient). "
        f"Charter FFA P&L uses cargo_size as denominator (not delivered "
        f"volume), introducing an additional ≈{residual_pct:.1f}% approximation."
    )

    # Settlement basis std: analytic from largest-impact leg
    col_map_eff = {
        "hh": "HH_Price", "jkm": "JKM_Price",
        "charter": "Charter_Rate", "fx": "USD_JPY",
    }
    max_basis = 0.0
    variance_ratios: Dict[str, float] = {}
    if adjustments and scenarios is not None:
        for leg_name, adj in adjustments.items():
            if adj is not None:
                col = col_map_eff.get(leg_name)
                if col and col in scenarios.columns:
                    spot_std = float(np.std(scenarios[col].values, ddof=1))
                    basis = spot_std * (1.0 - adj.sigma_scale)
                    max_basis = max(max_basis, basis)
                    variance_ratios[leg_name] = adj.variance_ratio

    return HedgeEffectiveness(
        variance_reduction=1.0 - (var_h / var_uh) if var_uh > 0 else 0.0,
        var_reduction=var5_h - var5_uh,
        cvar_reduction=cvar_h - cvar_uh,
        hedge_cost=mean_uh - mean_h,
        sharpe_unhedged=sharpe_uh,
        sharpe_hedged=sharpe_h,
        sharpe_improvement=sharpe_h - sharpe_uh,
        prob_loss_change=(
            float(np.mean(hedged_spread < 0))
            - float(np.mean(unhedged_spread < 0))
        ),
        jkm_effective_coverage=mean_coverage,
        basis_risk_note=basis_note,
        settlement_basis_std=max_basis,
        asian_variance_ratios=variance_ratios,
    )


# =============================================================================
# 8. Hedge Ratio Sensitivity Sweep
# =============================================================================

def compute_ratio_sensitivity(
    spec: SwapSpec,
    rates: Dict[str, float],
    scenarios: pd.DataFrame,
    route_results: List[MCRouteResult],
    optimal: OptimalStrategyResult,
    ratios: Optional[List[float]] = None,
    seed: int = 42,
    eff_prices: Optional[Dict[str, np.ndarray]] = None,
) -> List[RatioSensitivityRow]:
    """
    Sweep over uniform hedge ratios to show how effectiveness metrics change.

    At each ratio h, all enabled legs are set to h (uniform sweep for
    comparability across legs).  The full P&L overlay is re-computed cheaply
    via NumPy broadcasting.

    Parameters
    ----------
    eff_prices : dict or None
        Effective (Asian-adjusted) price arrays keyed by leg name.

    Returns
    -------
    List[RatioSensitivityRow] sorted by ascending hedge ratio.
    """
    ratios = ratios or [0.0, 0.25, 0.50, 0.75, 1.0]
    unhedged = optimal.optimal_spread
    rng = np.random.default_rng(seed)
    rows: List[RatioSensitivityRow] = []

    for h in ratios:
        swept_spec = SwapSpec(
            mode=spec.mode,
            hh=LegSpec(
                enabled=spec.hh.enabled,
                hedge_ratio=h,
                swap_rate=spec.hh.swap_rate,
                settlement=spec.hh.settlement,
                averaging_start_day=spec.hh.averaging_start_day,
                averaging_days=spec.hh.averaging_days,
            ),
            jkm=LegSpec(
                enabled=spec.jkm.enabled,
                hedge_ratio=h,
                swap_rate=spec.jkm.swap_rate,
                settlement=spec.jkm.settlement,
                averaging_start_day=spec.jkm.averaging_start_day,
                averaging_days=spec.jkm.averaging_days,
            ),
            charter=LegSpec(
                enabled=spec.charter.enabled,
                hedge_ratio=h,
                swap_rate=spec.charter.swap_rate,
                settlement=spec.charter.settlement,
            ),
            fx=LegSpec(
                enabled=spec.fx.enabled,
                hedge_ratio=h,
                swap_rate=spec.fx.swap_rate,
                settlement=spec.fx.settlement,
            ),
            notional_mmbtu=spec.notional_mmbtu,
            basis_noise_std=spec.basis_noise_std,
        )
        pnl, _ = compute_swap_pnl(
            swept_spec, rates, scenarios, route_results, optimal, rng,
            eff_prices=eff_prices,
        )
        hedged = unhedged + pnl

        var5 = float(np.percentile(hedged, 5))
        tail = hedged[hedged <= var5]
        cvar = float(np.mean(tail)) if len(tail) > 0 else var5

        var_h  = float(np.var(hedged,    ddof=1))
        var_uh = float(np.var(unhedged,  ddof=1))

        rows.append(RatioSensitivityRow(
            hedge_ratio=h,
            var_5pct=var5,
            cvar_5pct=cvar,
            variance_reduction=1.0 - (var_h / var_uh) if var_uh > 0 else 0.0,
            hedge_cost=float(np.mean(unhedged)) - float(np.mean(hedged)),
            prob_positive=float(np.mean(hedged > 0)),
        ))

    return rows


# =============================================================================
# 9. Per-Leg P&L Attribution
# =============================================================================

def compute_per_leg_pnl(
    spec: SwapSpec,
    rates: Dict[str, float],
    scenarios: pd.DataFrame,
    route_results: List[MCRouteResult],
    optimal: OptimalStrategyResult,
    eff_prices: Optional[Dict[str, np.ndarray]] = None,
) -> List[PerLegPnL]:
    """
    Compute isolated P&L statistics for each swap / FFA leg.

    Charter FFA P&L is converted to $/MMBtu (via rt_days / cargo_size) so all
    legs are expressed on a consistent spread-contribution basis.

    Parameters
    ----------
    eff_prices : dict or None
        Effective (Asian-adjusted) price arrays keyed by leg name.
        If None, raw scenario columns are used (European behavior).

    Returns
    -------
    List[PerLegPnL] in order: hh, jkm, charter, fx.
    """
    _ep = eff_prices or {}
    hh_price     = _ep.get("hh",      scenarios["HH_Price"].values)
    jkm_price    = _ep.get("jkm",     scenarios["JKM_Price"].values)
    charter_rate = _ep.get("charter",  scenarios["Charter_Rate"].values)
    usd_jpy      = _ep.get("fx",      scenarios["USD_JPY"].values)
    cargo_size   = spec.notional_mmbtu
    n = len(scenarios)

    rt_days = _build_rt_days_optimal(route_results, optimal.chosen_route_idx)

    def _stats(leg: LegSpec, leg_name: str, mc_mean: float) -> PerLegPnL:
        swap_rate = rates[leg_name]
        if not leg.enabled:
            return PerLegPnL(
                leg=leg_name,
                enabled=False,
                swap_rate=swap_rate,
                mc_mean=mc_mean,
                implied_cost=0.0,
                hedge_ratio=leg.hedge_ratio,
                pnl_mean=0.0,
                pnl_std=0.0,
                pnl_p05=0.0,
                pnl_p95=0.0,
            )

        if leg_name == "hh":
            arr = leg.hedge_ratio * (hh_price - swap_rate)
        elif leg_name == "jkm":
            arr = leg.hedge_ratio * (swap_rate - jkm_price)
        elif leg_name == "charter":
            ffa_day = leg.hedge_ratio * (charter_rate - swap_rate)
            arr = ffa_day * rt_days / cargo_size
        elif leg_name == "fx":
            fx_ref = swap_rate if swap_rate > 0 else 1.0
            arr = leg.hedge_ratio * (usd_jpy - swap_rate) / fx_ref
        else:
            arr = np.zeros(n)

        p05 = float(np.percentile(arr, 5))
        p95 = float(np.percentile(arr, 95))
        return PerLegPnL(
            leg=leg_name,
            enabled=True,
            swap_rate=swap_rate,
            mc_mean=mc_mean,
            implied_cost=swap_rate - mc_mean,
            hedge_ratio=leg.hedge_ratio,
            pnl_mean=float(np.mean(arr)),
            pnl_std=float(np.std(arr, ddof=1)),
            pnl_p05=p05,
            pnl_p95=p95,
        )

    mc_means = {
        "hh":      float(np.mean(hh_price)),
        "jkm":     float(np.mean(jkm_price)),
        "charter": float(np.mean(charter_rate)),
        "fx":      float(np.mean(usd_jpy)),
    }

    return [
        _stats(spec.hh,      "hh",      mc_means["hh"]),
        _stats(spec.jkm,     "jkm",     mc_means["jkm"]),
        _stats(spec.charter, "charter", mc_means["charter"]),
        _stats(spec.fx,      "fx",      mc_means["fx"]),
    ]


# =============================================================================
# 10. Main Orchestrator
# =============================================================================

def run_swap_overlay(
    mc_output: MCSpreadOutput,
    spec: Optional[SwapSpec] = None,
    step3_estimates: Optional[List] = None,
    seed: int = 42,
    output_dir: Optional[str] = None,
) -> HedgedOutput:
    """
    Full swap overlay pipeline.

    Reads MCSpreadOutput, applies the swap / FFA P&L on top of the Optimal
    Strategy spread, and returns a HedgedOutput with full effectiveness metrics.

    Parameters
    ----------
    mc_output : MCSpreadOutput
        Output from run_mc_spread().  Uses scenarios_enriched (for raw price
        columns), route_results (for rt_days and delivered_volume), and
        optimal_strategy (for optimal_spread / optimal_tce / chosen_route_idx).
    spec : SwapSpec or None
        Hedging configuration.  None → build from config.DEFAULT_SWAP_SPEC.
    step3_estimates : list of ParameterDistribution or None
        Step 3 parameter estimates.  Required for Asian swap settlement
        (provides κ for OU variance ratio computation).  If None, all legs
        behave as European (no Asian adjustment).
    seed : int
        RNG seed for optional basis noise.
    output_dir : str or None
        If provided, persist a Markdown report to this directory.

    Returns
    -------
    HedgedOutput
    """
    spec = spec if spec is not None else _build_spec_from_config()

    scenarios     = mc_output.scenarios_enriched
    optimal       = mc_output.optimal_strategy
    route_results = mc_output.route_results

    # Asian adjustment: build variance-compressed effective price arrays
    from .asian_adjustment import build_asian_adjustments, to_asian_equivalent, validate_asian_adjustments

    adjustments = build_asian_adjustments(step3_estimates, spec) if step3_estimates else {}

    # Sanity checks (Step 6a)
    if adjustments:
        adj_warnings = validate_asian_adjustments(adjustments)
        for w in adj_warnings:
            print(f"  [WARN] Asian adjustment: {w}")

    col_map: Dict[str, str] = {
        "hh": "HH_Price", "jkm": "JKM_Price",
        "charter": "Charter_Rate", "fx": "USD_JPY",
    }
    eff_prices: Dict[str, np.ndarray] = {}
    for leg_name, col in col_map.items():
        adj = adjustments.get(leg_name)
        if adj is not None:
            eff_prices[leg_name] = to_asian_equivalent(
                scenarios[col].values, adj.sigma_scale
            )
        else:
            eff_prices[leg_name] = scenarios[col].values

    # Step 1: Resolve fixed swap rates (uses eff_prices for auto mode)
    rates = resolve_swap_rates(spec, scenarios, eff_prices=eff_prices)

    # Step 2: Vectorised swap P&L (all N scenarios in one NumPy pass)
    rng = np.random.default_rng(seed)
    total_pnl, rt_days = compute_swap_pnl(
        spec, rates, scenarios, route_results, optimal, rng,
        eff_prices=eff_prices,
    )

    # Step 3: Overlay → hedged spread and TCE
    hedged_spread, hedged_tce = overlay_on_spread(
        optimal.optimal_spread,
        total_pnl,
        rt_days,
        spec.notional_mmbtu,
    )

    # Step 4a: Hedge effectiveness
    effectiveness = compute_hedge_effectiveness(
        optimal.optimal_spread, hedged_spread, spec, route_results,
        adjustments=adjustments, scenarios=scenarios,
    )

    # Step 4b: Hedge ratio sensitivity sweep
    ratio_sensitivity = compute_ratio_sensitivity(
        spec, rates, scenarios, route_results, optimal, seed=seed,
        eff_prices=eff_prices,
    )

    # Per-leg P&L attribution
    per_leg = compute_per_leg_pnl(
        spec, rates, scenarios, route_results, optimal,
        eff_prices=eff_prices,
    )

    result = HedgedOutput(
        swap_spec=spec,
        swap_rates=rates,
        hedged_spread=hedged_spread,
        hedged_tce=hedged_tce,
        hedged_stats_spread=compute_distribution_stats(hedged_spread),
        hedged_stats_tce=compute_distribution_stats(hedged_tce),
        unhedged_stats_spread=optimal.stats_optimal_spread,
        unhedged_stats_tce=optimal.stats_optimal_tce,
        effectiveness=effectiveness,
        ratio_sensitivity=ratio_sensitivity,
        per_leg_pnl=per_leg,
    )

    if output_dir:
        _persist_hedge_report(result, output_dir)

    return result


def _build_spec_from_config() -> SwapSpec:
    """Construct a SwapSpec from config.DEFAULT_SWAP_SPEC."""
    cfg = config.DEFAULT_SWAP_SPEC

    def _leg(d: dict) -> LegSpec:
        return LegSpec(
            enabled=d.get("enabled", False),
            hedge_ratio=d.get("hedge_ratio", 0.8),
            swap_rate=d.get("swap_rate", None),
            settlement=d.get("settlement", "european"),
            averaging_start_day=d.get("averaging_start_day", 25),
            averaging_days=d.get("averaging_days", 20),
        )

    return SwapSpec(
        mode=cfg.get("mode", "auto"),
        hh=_leg(cfg.get("hh", {})),
        jkm=_leg(cfg.get("jkm", {})),
        charter=_leg(cfg.get("charter", {})),
        fx=_leg(cfg.get("fx", {})),
        notional_mmbtu=cfg.get("notional_mmbtu", config.STANDARD_CARGO_SIZE_MMBTU),
        basis_noise_std=cfg.get("basis_noise_std", 0.0),
    )


# =============================================================================
# 11. Console Summary
# =============================================================================

def print_swap_summary(output: HedgedOutput) -> None:
    """Print a concise swap overlay summary matching the project's visual style."""
    eff = output.effectiveness
    uh  = output.unhedged_stats_spread
    h   = output.hedged_stats_spread

    print("\n" + "=" * 64)
    print("  SWAP OVERLAY — HEDGE EFFECTIVENESS  (Optimal Spread)")
    print("=" * 64)

    print(f"\n  Mode: {output.swap_spec.mode}  |  "
          f"Notional: {output.swap_spec.notional_mmbtu:,.0f} MMBtu")

    # ── Settlement structure ──
    settle_parts = []
    for leg_name in ("hh", "jkm"):
        leg = getattr(output.swap_spec, leg_name)
        if leg.enabled and leg.settlement == "asian":
            vr = eff.asian_variance_ratios.get(leg_name)
            vr_str = f"{vr:.2f}" if vr is not None else "n/a"
            settle_parts.append(f"{leg_name.upper()}={vr_str}")
    if settle_parts:
        leg_ref = getattr(output.swap_spec, "hh")
        print(f"  Settlement: asian "
              f"(\u0394={leg_ref.averaging_days}d, start=d{leg_ref.averaging_start_day})"
              f"  |  Variance ratio: {', '.join(settle_parts)}")
    else:
        print(f"  Settlement: european")

    # ── Per-leg configuration ──
    print(f"\n  {'Leg':<10s}  {'Status':<5s}  {'Swap Rate':>12s}  "
          f"{'h':>6s}  {'MC Mean':>10s}  {'Impl. Cost':>12s}")
    print(f"  {'─' * 64}")
    for lp in output.per_leg_pnl:
        status = "ON " if lp.enabled else "OFF"
        cost_str = f"{lp.implied_cost:>+10.3f}" if lp.enabled else "       n/a"
        print(f"  {lp.leg:<10s}  {status:<5s}  {lp.swap_rate:>12.3f}  "
              f"{lp.hedge_ratio:>5.0%}  {lp.mc_mean:>10.3f}  {cost_str}")

    # ── Distribution comparison ──
    print(f"\n  {'Metric':<26s}  {'Unhedged':>10s}  {'Hedged':>10s}  {'Δ':>10s}")
    print(f"  {'─' * 60}")
    rows = [
        ("Mean ($/MMBtu)",    f"{uh.mean:>+10.3f}", f"{h.mean:>+10.3f}",
         f"{h.mean - uh.mean:>+10.3f}"),
        ("Std Dev",           f"{uh.std:>10.3f}",   f"{h.std:>10.3f}",
         f"{h.std - uh.std:>+10.3f}"),
        ("P50 (Median)",      f"{uh.median:>+10.3f}", f"{h.median:>+10.3f}",
         f"{h.median - uh.median:>+10.3f}"),
        ("VaR 5% ($/MMBtu)",  f"{uh.var_5pct:>+10.3f}", f"{h.var_5pct:>+10.3f}",
         f"{h.var_5pct - uh.var_5pct:>+10.3f}"),
        ("CVaR 5% ($/MMBtu)", f"{uh.cvar_5pct:>+10.3f}", f"{h.cvar_5pct:>+10.3f}",
         f"{h.cvar_5pct - uh.cvar_5pct:>+10.3f}"),
        ("P(Spread > 0)",     f"{uh.prob_positive:>10.1%}", f"{h.prob_positive:>10.1%}",
         f"{h.prob_positive - uh.prob_positive:>+10.1%}"),
    ]
    for label, u_val, h_val, delta in rows:
        print(f"  {label:<26s}  {u_val}  {h_val}  {delta}")

    # ── Effectiveness summary ──
    print(f"\n  Effectiveness:")
    print(f"    Variance reduction  {eff.variance_reduction:>+8.1%}")
    print(f"    VaR reduction       {eff.var_reduction:>+8.3f} $/MMBtu")
    print(f"    CVaR reduction      {eff.cvar_reduction:>+8.3f} $/MMBtu")
    print(f"    Hedge cost          {eff.hedge_cost:>+8.3f} $/MMBtu  "
          f"({'premium paid' if eff.hedge_cost > 0 else 'premium received'})")
    print(f"    Sharpe (unhedged)   {eff.sharpe_unhedged:>8.3f}")
    print(f"    Sharpe (hedged)     {eff.sharpe_hedged:>8.3f}  "
          f"({eff.sharpe_improvement:>+.3f})")
    print(f"    P(loss) change      {eff.prob_loss_change:>+8.1%}")

    # ── Ratio sensitivity ──
    print(f"\n  Hedge ratio sensitivity:")
    print(f"    {'h':>5s}  {'VaR 5%':>9s}  {'CVaR 5%':>9s}  "
          f"{'VarRed':>7s}  {'Cost':>8s}  {'P(>0)':>6s}")
    for row in output.ratio_sensitivity:
        print(f"    {row.hedge_ratio:>4.0%}  {row.var_5pct:>+9.3f}  "
              f"{row.cvar_5pct:>+9.3f}  {row.variance_reduction:>6.1%}  "
              f"{row.hedge_cost:>+8.3f}  {row.prob_positive:>5.1%}")

    # ── Basis risk note ──
    print(f"\n  Structural basis risk:")
    print(f"    JKM effective coverage: "
          f"{eff.jkm_effective_coverage * 100:.1f}% of Netback JKM exposure.")
    note_short = eff.basis_risk_note.split(".")[0] + "."
    print(f"    {note_short}")

    print("\n" + "=" * 64)


# =============================================================================
# 12. Persistence — Markdown Report
# =============================================================================

def _persist_hedge_report(output: HedgedOutput, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, "swap_overlay_report.md")
    _write_hedge_report(output, md_path)
    print(f"\n  Swap overlay report persisted: {md_path}")


def _write_hedge_report(output: HedgedOutput, path: str) -> None:
    eff  = output.effectiveness
    uh   = output.unhedged_stats_spread
    h    = output.hedged_stats_spread
    uh_t = output.unhedged_stats_tce
    h_t  = output.hedged_stats_tce
    spec = output.swap_spec

    lines = [
        "# Swap Overlay — Hedge Effectiveness Report",
        "",
        "## Configuration",
        "",
        f"- **Mode**: `{spec.mode}`",
        f"- **Notional**: {spec.notional_mmbtu:,.0f} MMBtu",
        f"- **Basis noise std**: {spec.basis_noise_std}",
        "",
        "### Swap Legs",
        "",
        "| Leg | Enabled | Hedge Ratio | Swap Rate | MC Mean | Implied Cost |",
        "| --- | :---: | ---: | ---: | ---: | ---: |",
    ]
    for lp in output.per_leg_pnl:
        lines.append(
            f"| {lp.leg} | {'✓' if lp.enabled else '–'} "
            f"| {lp.hedge_ratio:.0%} | {lp.swap_rate:.3f} "
            f"| {lp.mc_mean:.3f} | {lp.implied_cost:+.3f} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Distribution Comparison — Optimal Spread ($/MMBtu)",
        "",
        "| Metric | Unhedged | Hedged | Δ |",
        "| --- | ---: | ---: | ---: |",
        f"| Mean | {uh.mean:+.3f} | {h.mean:+.3f} | {h.mean - uh.mean:+.3f} |",
        f"| Std Dev | {uh.std:.3f} | {h.std:.3f} | {h.std - uh.std:+.3f} |",
        f"| Median (P50) | {uh.median:+.3f} | {h.median:+.3f} | {h.median - uh.median:+.3f} |",
        f"| P05 (VaR 5%) | {uh.p05:+.3f} | {h.p05:+.3f} | {h.p05 - uh.p05:+.3f} |",
        f"| CVaR 5% | {uh.cvar_5pct:+.3f} | {h.cvar_5pct:+.3f} | {h.cvar_5pct - uh.cvar_5pct:+.3f} |",
        f"| Skewness | {uh.skewness:+.3f} | {h.skewness:+.3f} | {h.skewness - uh.skewness:+.3f} |",
        f"| Kurtosis | {uh.kurtosis:+.3f} | {h.kurtosis:+.3f} | {h.kurtosis - uh.kurtosis:+.3f} |",
        f"| P(Spread > 0) | {uh.prob_positive:.1%} | {h.prob_positive:.1%} | {h.prob_positive - uh.prob_positive:+.1%} |",
        "",
        "## Distribution Comparison — Optimal TCE ($/day)",
        "",
        "| Metric | Unhedged | Hedged | Δ |",
        "| --- | ---: | ---: | ---: |",
        f"| Mean | {uh_t.mean:+,.0f} | {h_t.mean:+,.0f} | {h_t.mean - uh_t.mean:+,.0f} |",
        f"| Std Dev | {uh_t.std:,.0f} | {h_t.std:,.0f} | {h_t.std - uh_t.std:+,.0f} |",
        f"| P05 | {uh_t.p05:+,.0f} | {h_t.p05:+,.0f} | {h_t.p05 - uh_t.p05:+,.0f} |",
        f"| P95 | {uh_t.p95:+,.0f} | {h_t.p95:+,.0f} | {h_t.p95 - uh_t.p95:+,.0f} |",
        f"| P(TCE > 0) | {uh_t.prob_positive:.1%} | {h_t.prob_positive:.1%} | {h_t.prob_positive - uh_t.prob_positive:+.1%} |",
        "",
        "---",
        "",
        "## Hedge Effectiveness",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Variance Reduction | {eff.variance_reduction:.1%} |",
        f"| VaR Reduction ($/MMBtu) | {eff.var_reduction:+.3f} |",
        f"| CVaR Reduction ($/MMBtu) | {eff.cvar_reduction:+.3f} |",
        f"| Hedge Cost ($/MMBtu) | {eff.hedge_cost:+.3f} |",
        f"| Sharpe (Unhedged) | {eff.sharpe_unhedged:.3f} |",
        f"| Sharpe (Hedged) | {eff.sharpe_hedged:.3f} |",
        f"| Sharpe Improvement | {eff.sharpe_improvement:+.3f} |",
        f"| P(Loss) Change | {eff.prob_loss_change:+.1%} |",
        f"| JKM Effective Coverage | {eff.jkm_effective_coverage:.1%} |",
        "",
        "---",
        "",
        "## Hedge Ratio Sensitivity",
        "",
        "| h | VaR 5% | CVaR 5% | Var Reduction | Hedge Cost | P(>0) |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in output.ratio_sensitivity:
        lines.append(
            f"| {row.hedge_ratio:.0%} | {row.var_5pct:+.3f} | {row.cvar_5pct:+.3f} "
            f"| {row.variance_reduction:.1%} | {row.hedge_cost:+.3f} "
            f"| {row.prob_positive:.1%} |"
        )

    # ── Settlement Structure section ──
    lines += [
        "",
        "---",
        "",
        "## Settlement Structure",
        "",
        "| Leg | Settlement | Avg Start | Avg Days | Var Ratio | \u03c3 Scale |",
        "| --- | :---: | ---: | ---: | ---: | ---: |",
    ]
    for leg_name in ("hh", "jkm", "charter", "fx"):
        leg = getattr(spec, leg_name)
        if leg.settlement == "asian":
            vr = eff.asian_variance_ratios.get(leg_name, 0.0)
            ss = vr ** 0.5 if vr > 0 else 1.0
            lines.append(
                f"| {leg_name} | asian | {leg.averaging_start_day} "
                f"| {leg.averaging_days} | {vr:.3f} | {ss:.3f} |"
            )
        else:
            lines.append(
                f"| {leg_name} | european | \u2013 | \u2013 | 1.000 | 1.000 |"
            )
    lines.append("")
    lines.append(
        f"Settlement basis std (spot vs average): "
        f"${eff.settlement_basis_std:.3f}/MMBtu"
    )

    lines += [
        "",
        "---",
        "",
        "## Structural Basis Risk",
        "",
        f"> {eff.basis_risk_note}",
        "",
    ]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
