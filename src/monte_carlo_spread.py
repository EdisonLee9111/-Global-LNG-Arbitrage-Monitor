"""
monte_carlo_spread.py — Monte Carlo Spread Distribution Engine (Layer 2)
========================================================================
Bridges Step 5 correlated scenarios into the LNG economics engine,
transforming single-point Netback values into full probability distributions.

Architecture
------------
Phase A (scalar, per route):  Resolve deterministic voyage constants from config.
Phase B (vectorized, N=10,000): Broadcast Netback formula over all scenarios.
Phase C (cross-route):         Real Option optimal strategy via max().

Output metrics:
  - Spread distribution ($/MMBtu) per route
  - TCE distribution ($/day) per route — time-normalized profit
  - JERA domestic margin (JPY/MMBtu) — diversion decision signal
  - Optimal Strategy spread — destination flexibility option premium
  - VaR / CVaR / quantiles / success probabilities
  - First-order sensitivity (which factor drives spread variance)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from . import config


# =============================================================================
# 1. Data Structures
# =============================================================================

@dataclass
class RouteConstants:
    """Deterministic voyage parameters pre-resolved from config.ROUTES."""
    route_name: str
    label: str
    dest_price_col: str
    distance_nm: float
    base_laden_days: float
    base_ballast_days: float
    port_days: float
    canal_fee: float


@dataclass
class DistributionStats:
    """Summary statistics for a value distribution."""
    mean: float
    median: float
    std: float
    p05: float
    p25: float
    p75: float
    p95: float
    var_5pct: float
    cvar_5pct: float
    prob_positive: float
    prob_above_1: float
    skewness: float
    kurtosis: float


@dataclass
class MCRouteResult:
    """Monte Carlo results for a single route."""
    route: RouteConstants
    netback: np.ndarray
    spread: np.ndarray
    tce: np.ndarray
    delivered_volume: np.ndarray
    total_rt_days: np.ndarray
    stats_spread: Optional[DistributionStats] = None
    stats_tce: Optional[DistributionStats] = None


@dataclass
class JERAMarginResult:
    """JERA domestic import margin analysis."""
    import_cost_jpy: np.ndarray
    domestic_profit_jpy: np.ndarray
    divert_flag: np.ndarray
    divert_probability: float
    domestic_revenue_jpy: float


@dataclass
class OptimalStrategyResult:
    """Real Option valuation across routes."""
    optimal_spread: np.ndarray
    optimal_tce: np.ndarray
    chosen_route_idx: np.ndarray
    route_labels: List[str]
    route_selection_prob: Dict[str, float]
    option_premium_spread: float
    option_premium_tce: float
    stats_optimal_spread: Optional[DistributionStats] = None
    stats_optimal_tce: Optional[DistributionStats] = None


@dataclass
class SensitivityResult:
    """Single factor's contribution to spread variance."""
    factor: str
    pearson_corr: float
    spearman_corr: float
    variance_contribution_pct: float


@dataclass
class MCSpreadOutput:
    """Top-level container for all MC spread analysis results."""
    n_scenarios: int
    route_results: List[MCRouteResult]
    jera_margin: JERAMarginResult
    optimal_strategy: OptimalStrategyResult
    sensitivity: Dict[str, List[SensitivityResult]]
    scenarios_enriched: pd.DataFrame


# =============================================================================
# 2. Utility — Distribution Statistics
# =============================================================================

def compute_distribution_stats(values: np.ndarray) -> DistributionStats:
    """Compute comprehensive statistics for an array of MC outcomes."""
    p05, p25, p50, p75, p95 = np.percentile(values, [5, 25, 50, 75, 95])
    var_5 = p05
    tail = values[values <= p05]
    cvar_5 = float(np.mean(tail)) if len(tail) > 0 else var_5

    return DistributionStats(
        mean=float(np.mean(values)),
        median=float(p50),
        std=float(np.std(values, ddof=1)),
        p05=float(p05),
        p25=float(p25),
        p75=float(p75),
        p95=float(p95),
        var_5pct=float(var_5),
        cvar_5pct=float(cvar_5),
        prob_positive=float(np.mean(values > 0)),
        prob_above_1=float(np.mean(values > 1.0)),
        skewness=float(sp_stats.skew(values)),
        kurtosis=float(sp_stats.kurtosis(values)),
    )


# =============================================================================
# 3. Phase A — Resolve Deterministic Route Constants
# =============================================================================

def resolve_route_constants(
    route_name: str,
    label: str,
    dest_price_col: str,
) -> RouteConstants:
    """
    Extract deterministic voyage parameters from config.ROUTES.

    These values are constant across all MC scenarios; stochastic
    variation enters only through Voyage_Delay, BOG_Rate, etc.
    """
    if route_name not in config.ROUTES:
        raise ValueError(
            f"Unknown route: {route_name}. "
            f"Available: {list(config.ROUTES.keys())}"
        )
    route = config.ROUTES[route_name]
    distance = route["distance_nm"]

    return RouteConstants(
        route_name=route_name,
        label=label,
        dest_price_col=dest_price_col,
        distance_nm=distance,
        base_laden_days=distance / (config.LADEN_SPEED * 24.0),
        base_ballast_days=distance / (config.BALLAST_SPEED * 24.0),
        port_days=config.LOADING_TIME + config.UNLOADING_TIME,
        canal_fee=route.get("canal_fee", 0),
    )


# =============================================================================
# 4. Phase B — Vectorized Netback / Spread / TCE
# =============================================================================

def vectorized_netback(
    scenarios: pd.DataFrame,
    rc: RouteConstants,
    cargo_size: float = config.STANDARD_CARGO_SIZE_MMBTU,
    liquefaction: float = config.DEFAULT_LIQUEFACTION_COST,
) -> MCRouteResult:
    """
    Vectorized Netback calculation over all MC scenarios.

    Replicates ``LNGCalculator.calculate_netback()`` exactly, using
    NumPy broadcasting instead of Python loops.  On a 10,000-scenario
    DataFrame this runs in < 1 ms (vs ~seconds with a Python loop).

    Formula (per loaded MMBtu, industry-standard approximation)
    ------------------------------------------------------------
    laden_days      = base_laden_days + Voyage_Delay
    remaining_ratio = (1 - BOG_Rate) ^ laden_days
    delivered       = cargo × remaining_ratio
    bog_ratio       = 1 - remaining_ratio

    revenue_per_loaded = dest_price × (1 - bog_ratio)
    shipping_per_del   = RT_days × (Charter + Fuel) / delivered
    canal_per_del      = canal_fee / delivered

    netback = revenue_per_loaded - shipping_per_del - canal_per_del - liquefaction
    spread  = netback - HH_Price
    TCE     = (spread × cargo_size) / RT_days          [$/day]
    """
    dest_price = scenarios[rc.dest_price_col].values
    hh_price   = scenarios["HH_Price"].values
    charter    = scenarios["Charter_Rate"].values
    fuel       = scenarios["Fuel_Cost"].values
    bog_rate   = scenarios["BOG_Rate"].values
    delay      = scenarios["Voyage_Delay"].values

    # ── voyage timing ──
    laden_days    = rc.base_laden_days + delay
    total_rt_days = laden_days + rc.base_ballast_days + rc.port_days

    # ── BOG: exponential decay  V_remaining = V0 × (1 - r)^d ──
    remaining_ratio = (1.0 - bog_rate) ** laden_days
    bog_ratio       = 1.0 - remaining_ratio
    delivered       = cargo_size * remaining_ratio

    # ── costs per unit (allocated to delivered volume) ──
    total_shipping     = total_rt_days * (charter + fuel)
    shipping_per_mmbtu = total_shipping / delivered
    canal_per_mmbtu    = rc.canal_fee / delivered

    # ── Netback (per loaded MMBtu) ──
    revenue_per_loaded = dest_price * (1.0 - bog_ratio)
    netback = (
        revenue_per_loaded
        - shipping_per_mmbtu
        - canal_per_mmbtu
        - liquefaction
    )

    # ── Arbitrage spread ──
    spread = netback - hh_price

    # ── TCE: total cargo profit / round-trip days ──
    tce = (spread * cargo_size) / total_rt_days

    return MCRouteResult(
        route=rc,
        netback=netback,
        spread=spread,
        tce=tce,
        delivered_volume=delivered,
        total_rt_days=total_rt_days,
        stats_spread=compute_distribution_stats(spread),
        stats_tce=compute_distribution_stats(tce),
    )


# =============================================================================
# 5. JERA Domestic Margin
# =============================================================================

def compute_jera_domestic_margin(
    scenarios: pd.DataFrame,
    domestic_revenue_jpy: float = config.JERA_DOMESTIC_REVENUE_JPY,
) -> JERAMarginResult:
    """
    Assess JERA's domestic import profitability under each scenario.

    JERA buys LNG at JKM (USD), ships to Japan, sells domestically in JPY.
      Import_Cost_JPY     = JKM × USD_JPY
      Domestic_Profit_JPY = domestic_revenue - Import_Cost_JPY

    When profit < 0 → JERA should divert the cargo (sell spot in EU/Asia
    rather than importing at a loss).  The divert probability is a key
    market-structure signal for Asian LNG flows.
    """
    jkm       = scenarios["JKM_Price"].values
    usd_jpy   = scenarios["USD_JPY"].values

    import_cost_jpy     = jkm * usd_jpy
    domestic_profit_jpy = domestic_revenue_jpy - import_cost_jpy
    divert_flag         = domestic_profit_jpy < 0

    return JERAMarginResult(
        import_cost_jpy=import_cost_jpy,
        domestic_profit_jpy=domestic_profit_jpy,
        divert_flag=divert_flag,
        divert_probability=float(np.mean(divert_flag)),
        domestic_revenue_jpy=domestic_revenue_jpy,
    )


# =============================================================================
# 6. Phase C — Optimal Strategy (Real Option)
# =============================================================================

def compute_optimal_strategy(
    route_results: List[MCRouteResult],
) -> OptimalStrategyResult:
    """
    Real Option valuation: at each scenario the trader picks the
    most profitable destination (or chooses not to ship at all).

      Optimal_Spread[i] = max(Spread_EU[i], Spread_Asia[i], ..., 0)

    The "0" floor represents the no-go option (don't ship / sell FOB).
    The option premium — E[Optimal] − max(E[individual]) — quantifies
    the pure value of destination flexibility.
    """
    n = len(route_results[0].spread)
    n_routes = len(route_results)

    # (n_routes, n) matrices — each row is one route's outcomes
    spreads = np.stack([rr.spread for rr in route_results], axis=0)
    tces    = np.stack([rr.tce    for rr in route_results], axis=0)

    # append no-go option (spread=0, tce=0) as the last "route"
    spreads_all = np.vstack([spreads, np.zeros((1, n))])
    tces_all    = np.vstack([tces,    np.zeros((1, n))])

    labels = [rr.route.label for rr in route_results] + ["No-Go"]

    # per-scenario optimal choice
    chosen_idx      = np.argmax(spreads_all, axis=0)
    optimal_spread  = spreads_all[chosen_idx, np.arange(n)]
    optimal_tce     = tces_all[chosen_idx,    np.arange(n)]

    # route selection probabilities
    route_probs: Dict[str, float] = {}
    for i, label in enumerate(labels):
        route_probs[label] = float(np.mean(chosen_idx == i))

    # option premium = E[optimal] - best individual E[spread]
    individual_spread_means = [float(np.mean(rr.spread)) for rr in route_results]
    individual_tce_means    = [float(np.mean(rr.tce))    for rr in route_results]

    best_individual_spread = max(individual_spread_means) if individual_spread_means else 0.0
    best_individual_tce    = max(individual_tce_means)    if individual_tce_means    else 0.0

    option_premium_spread = float(np.mean(optimal_spread)) - best_individual_spread
    option_premium_tce    = float(np.mean(optimal_tce))    - best_individual_tce

    return OptimalStrategyResult(
        optimal_spread=optimal_spread,
        optimal_tce=optimal_tce,
        chosen_route_idx=chosen_idx,
        route_labels=labels,
        route_selection_prob=route_probs,
        option_premium_spread=option_premium_spread,
        option_premium_tce=option_premium_tce,
        stats_optimal_spread=compute_distribution_stats(optimal_spread),
        stats_optimal_tce=compute_distribution_stats(optimal_tce),
    )


# =============================================================================
# 7. Sensitivity Analysis
# =============================================================================

def sensitivity_analysis(
    scenarios: pd.DataFrame,
    spread: np.ndarray,
) -> List[SensitivityResult]:
    """
    First-order sensitivity of spread to each input factor.

    Uses squared Spearman rank correlation as a proxy for variance
    contribution.  This captures monotonic nonlinear relationships
    (e.g. BOG's exponential effect) better than Pearson.  Results
    are normalized so contributions sum to 100 %.
    """
    results: List[SensitivityResult] = []
    for col in scenarios.columns:
        x = scenarios[col].values
        if np.std(x) < 1e-12:
            results.append(SensitivityResult(col, 0.0, 0.0, 0.0))
            continue

        pearson_r  = float(np.corrcoef(x, spread)[0, 1])
        spearman_r = float(sp_stats.spearmanr(x, spread).statistic)
        results.append(SensitivityResult(col, pearson_r, spearman_r, 0.0))

    # normalise variance contributions
    total_r2 = sum(r.spearman_corr ** 2 for r in results)
    if total_r2 > 0:
        for r in results:
            r.variance_contribution_pct = (r.spearman_corr ** 2 / total_r2) * 100.0

    results.sort(key=lambda r: r.variance_contribution_pct, reverse=True)
    return results


# =============================================================================
# 8. Top-Level Orchestrator
# =============================================================================

DEFAULT_MC_ROUTES: List[Tuple[str, str, str]] = [
    ("US_Gulf_to_Rotterdam",    "Europe (Rotterdam)",          "TTF_Price"),
    ("US_Gulf_to_Tokyo_Panama", "Asia (Tokyo via Panama)",     "JKM_Price"),
    ("US_Gulf_to_Tokyo_COGH",   "Asia (Tokyo via COGH)",       "JKM_Price"),
]


def run_mc_spread(
    scenarios: pd.DataFrame,
    cargo_size: float = config.STANDARD_CARGO_SIZE_MMBTU,
    liquefaction: float = config.DEFAULT_LIQUEFACTION_COST,
    jera_domestic_revenue_jpy: float = config.JERA_DOMESTIC_REVENUE_JPY,
    routes: Optional[List[Tuple[str, str, str]]] = None,
    output_dir: Optional[str] = None,
) -> MCSpreadOutput:
    """
    Full Monte Carlo spread pipeline.

    Parameters
    ----------
    scenarios : DataFrame
        10,000-row MC scenarios from Step 5, with columns:
        HH_Price, TTF_Price, JKM_Price, Charter_Rate,
        USD_JPY, Fuel_Cost, Voyage_Delay, BOG_Rate.
    cargo_size : float
        Standard cargo (MMBtu).
    liquefaction : float
        Liquefaction tolling fee ($/MMBtu).
    jera_domestic_revenue_jpy : float
        JERA's domestic gas revenue threshold (JPY/MMBtu).
    routes : list of (route_name, label, dest_price_col) tuples
        Routes to evaluate; defaults to EU + Asia-Panama + Asia-COGH.
    output_dir : str or None
        If provided, persist CSV + markdown report to this directory.

    Returns
    -------
    MCSpreadOutput
        Contains per-route distributions, JERA margin, optimal strategy,
        sensitivity analysis, and an enriched scenarios DataFrame.
    """
    routes = routes or DEFAULT_MC_ROUTES

    # Phase A: resolve deterministic constants per route
    route_constants = [resolve_route_constants(*r) for r in routes]

    # Phase B: vectorized Netback for each route
    route_results = [
        vectorized_netback(scenarios, rc, cargo_size, liquefaction)
        for rc in route_constants
    ]

    # JERA domestic margin
    jera = compute_jera_domestic_margin(scenarios, jera_domestic_revenue_jpy)

    # Phase C: optimal strategy (Real Option)
    optimal = compute_optimal_strategy(route_results)

    # Sensitivity analysis per route + optimal
    sens: Dict[str, List[SensitivityResult]] = {}
    for rr in route_results:
        sens[rr.route.label] = sensitivity_analysis(scenarios, rr.spread)
    sens["Optimal"] = sensitivity_analysis(scenarios, optimal.optimal_spread)

    # Enrich scenarios DataFrame with computed columns
    enriched = scenarios.copy()
    for rr in route_results:
        tag = _sanitize_label(rr.route.label)
        enriched[f"Spread_{tag}"]  = rr.spread
        enriched[f"Netback_{tag}"] = rr.netback
        enriched[f"TCE_{tag}"]     = rr.tce
    enriched["Optimal_Spread"]          = optimal.optimal_spread
    enriched["Optimal_TCE"]             = optimal.optimal_tce
    enriched["Chosen_Route"]            = optimal.chosen_route_idx
    enriched["JERA_Import_Cost_JPY"]    = jera.import_cost_jpy
    enriched["JERA_Domestic_Profit_JPY"] = jera.domestic_profit_jpy
    enriched["JERA_Divert"]             = jera.divert_flag

    output = MCSpreadOutput(
        n_scenarios=len(scenarios),
        route_results=route_results,
        jera_margin=jera,
        optimal_strategy=optimal,
        sensitivity=sens,
        scenarios_enriched=enriched,
    )

    if output_dir:
        _persist_mc_results(output, output_dir)

    return output


# =============================================================================
# 9. Console Summary
# =============================================================================

def print_mc_summary(output: MCSpreadOutput) -> None:
    """Print a concise console summary matching the project's visual style."""
    print("\n" + "=" * 64)
    print("  MONTE CARLO SPREAD DISTRIBUTION (Layer 2)")
    print("=" * 64)
    print(f"  Scenarios: {output.n_scenarios:,}")

    # ── per-route spread & TCE ──
    for rr in output.route_results:
        s = rr.stats_spread
        t = rr.stats_tce
        print(f"\n  {'─' * 58}")
        print(f"  {rr.route.label}")
        print(f"  {'─' * 58}")
        print(f"    Spread  mean=${s.mean:+.2f}  "
              f"P5=${s.p05:+.2f}  P50=${s.median:+.2f}  P95=${s.p95:+.2f}")
        print(f"    TCE     mean=${t.mean:>+,.0f}/day  "
              f"P5=${t.p05:>+,.0f}  P95=${t.p95:>+,.0f}")
        print(f"    P(arb>0)={s.prob_positive:.1%}  "
              f"P(arb>$1)={s.prob_above_1:.1%}  "
              f"VaR5%=${s.var_5pct:+.2f}  CVaR5%=${s.cvar_5pct:+.2f}")

    # ── JERA ──
    jera = output.jera_margin
    print(f"\n  {'─' * 58}")
    print(f"  JERA Domestic Margin")
    print(f"  {'─' * 58}")
    mean_profit = float(np.mean(jera.domestic_profit_jpy))
    print(f"    Revenue threshold: {jera.domestic_revenue_jpy:,.0f} JPY/MMBtu")
    print(f"    Mean import cost:  {float(np.mean(jera.import_cost_jpy)):,.0f} JPY/MMBtu")
    print(f"    Mean profit:       {mean_profit:+,.0f} JPY/MMBtu")
    print(f"    Divert probability: {jera.divert_probability:.1%}")

    # ── Optimal strategy ──
    opt = output.optimal_strategy
    s_opt = opt.stats_optimal_spread
    print(f"\n  {'─' * 58}")
    print(f"  Optimal Strategy (Real Option)")
    print(f"  {'─' * 58}")
    print(f"    Optimal spread  mean=${s_opt.mean:+.2f}  "
          f"P50=${s_opt.median:+.2f}  P95=${s_opt.p95:+.2f}")
    print(f"    Option premium (spread): ${opt.option_premium_spread:+.4f}/MMBtu")
    print(f"    Option premium (TCE):    ${opt.option_premium_tce:+,.0f}/day")
    print(f"    Route selection:")
    for label, prob in opt.route_selection_prob.items():
        bar = "█" * int(prob * 40)
        print(f"      {label:<28s} {prob:5.1%}  {bar}")

    # ── top-3 sensitivity for optimal spread ──
    print(f"\n  {'─' * 58}")
    print(f"  Sensitivity (Optimal Spread — top factors)")
    print(f"  {'─' * 58}")
    for sr in output.sensitivity.get("Optimal", [])[:5]:
        bar = "█" * int(sr.variance_contribution_pct / 2.5)
        print(f"    {sr.factor:<16s}  "
              f"rho={sr.spearman_corr:+.3f}  "
              f"var={sr.variance_contribution_pct:5.1f}%  {bar}")

    print("\n" + "=" * 64)


# =============================================================================
# 10. Persistence — CSV + Markdown Report
# =============================================================================

def _sanitize_label(label: str) -> str:
    """Convert route label to a safe column-name suffix."""
    return (
        label.replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
    )


def _persist_mc_results(output: MCSpreadOutput, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)

    csv_path = os.path.join(output_dir, "mc_spread_scenarios.csv")
    output.scenarios_enriched.to_csv(csv_path, index=False)

    md_path = os.path.join(output_dir, "mc_spread_report.md")
    _write_mc_report(output, md_path)

    print(f"\n  MC results persisted:")
    print(f"    CSV:  {csv_path}")
    print(f"    MD:   {md_path}")


def _write_mc_report(output: MCSpreadOutput, path: str) -> None:
    """Generate a detailed markdown report of the MC analysis."""
    lines = [
        "# Monte Carlo Spread Distribution Report",
        "",
        f"Scenarios: **{output.n_scenarios:,}**",
        "",
        "---",
        "",
    ]

    # ── per-route ──
    for rr in output.route_results:
        s = rr.stats_spread
        t = rr.stats_tce
        lines.extend([
            f"## {rr.route.label}",
            "",
            f"Route: `{rr.route.route_name}` "
            f"({rr.route.distance_nm:,.0f} nm, "
            f"base laden {rr.route.base_laden_days:.1f} d, "
            f"canal fee ${rr.route.canal_fee:,.0f})",
            "",
            "### Spread ($/MMBtu)",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Mean | ${s.mean:+.3f} |",
            f"| Median (P50) | ${s.median:+.3f} |",
            f"| Std Dev | ${s.std:.3f} |",
            f"| P05 | ${s.p05:+.3f} |",
            f"| P25 | ${s.p25:+.3f} |",
            f"| P75 | ${s.p75:+.3f} |",
            f"| P95 | ${s.p95:+.3f} |",
            f"| VaR (5%) | ${s.var_5pct:+.3f} |",
            f"| CVaR (5%) | ${s.cvar_5pct:+.3f} |",
            f"| P(Spread > 0) | {s.prob_positive:.1%} |",
            f"| P(Spread > $1) | {s.prob_above_1:.1%} |",
            f"| Skewness | {s.skewness:+.3f} |",
            f"| Kurtosis | {s.kurtosis:+.3f} |",
            "",
            "### TCE ($/day)",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Mean | ${t.mean:+,.0f} |",
            f"| Median | ${t.median:+,.0f} |",
            f"| P05 | ${t.p05:+,.0f} |",
            f"| P95 | ${t.p95:+,.0f} |",
            f"| P(TCE > 0) | {t.prob_positive:.1%} |",
            "",
            "---",
            "",
        ])

    # ── JERA ──
    jera = output.jera_margin
    mean_import  = float(np.mean(jera.import_cost_jpy))
    mean_profit  = float(np.mean(jera.domestic_profit_jpy))
    p05_profit   = float(np.percentile(jera.domestic_profit_jpy, 5))
    p95_profit   = float(np.percentile(jera.domestic_profit_jpy, 95))

    lines.extend([
        "## JERA Domestic Margin Analysis",
        "",
        "JERA imports LNG at JKM (USD), converts via USD/JPY, "
        "and sells domestically in JPY.  When the import cost exceeds "
        "domestic revenue, diversion to the spot market is optimal.",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Domestic Revenue | {jera.domestic_revenue_jpy:,.0f} JPY/MMBtu |",
        f"| Mean Import Cost | {mean_import:,.0f} JPY/MMBtu |",
        f"| Mean Domestic Profit | {mean_profit:+,.0f} JPY/MMBtu |",
        f"| P05 Domestic Profit | {p05_profit:+,.0f} JPY/MMBtu |",
        f"| P95 Domestic Profit | {p95_profit:+,.0f} JPY/MMBtu |",
        f"| Divert Probability | {jera.divert_probability:.1%} |",
        "",
        "---",
        "",
    ])

    # ── Optimal strategy ──
    opt = output.optimal_strategy
    s_opt = opt.stats_optimal_spread
    t_opt = opt.stats_optimal_tce

    lines.extend([
        "## Optimal Strategy (Real Option — Destination Flexibility)",
        "",
        "For each scenario the trader picks the route with the highest "
        "spread, or chooses *No-Go* if all routes are unprofitable.  "
        "The option premium is the additional value created by flexibility.",
        "",
        "### Route Selection Probabilities",
        "",
        "| Route | P(chosen) |",
        "| --- | ---: |",
    ])
    for label, prob in opt.route_selection_prob.items():
        lines.append(f"| {label} | {prob:.1%} |")

    lines.extend([
        "",
        "### Optimal Spread ($/MMBtu)",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Mean | ${s_opt.mean:+.3f} |",
        f"| Median | ${s_opt.median:+.3f} |",
        f"| P05 | ${s_opt.p05:+.3f} |",
        f"| P95 | ${s_opt.p95:+.3f} |",
        f"| P(Spread > 0) | {s_opt.prob_positive:.1%} |",
        "",
        f"**Option Premium (Spread)**: ${opt.option_premium_spread:+.4f}/MMBtu",
        "",
        f"**Option Premium (TCE)**: ${opt.option_premium_tce:+,.0f}/day",
        "",
        "---",
        "",
    ])

    # ── Sensitivity ──
    lines.extend([
        "## Sensitivity Analysis",
        "",
        "Variance contribution is based on squared Spearman rank correlation, "
        "normalised to 100 %.  This captures monotonic nonlinear effects "
        "(e.g. exponential BOG decay).",
        "",
    ])
    for route_label, sens_list in output.sensitivity.items():
        lines.extend([
            f"### {route_label}",
            "",
            "| Rank | Factor | Spearman rho | Variance % |",
            "| ---: | --- | ---: | ---: |",
        ])
        for rank, sr in enumerate(sens_list, 1):
            lines.append(
                f"| {rank} | {sr.factor} | {sr.spearman_corr:+.4f} "
                f"| {sr.variance_contribution_pct:.1f}% |"
            )
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
