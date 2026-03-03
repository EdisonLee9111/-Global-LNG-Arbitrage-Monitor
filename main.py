"""
main.py - Global LNG Arbitrage Monitor Main Program Entry
==========================================================
Integrates all modules and executes the following workflow:
1. Load/download market data (Henry Hub, TTF, JKM, USD/JPY)
2. Run LNG economics calculations (Netback, arbitrage window)
3. Run NLP macro sentiment analysis (central bank minutes)
4. Generate professional charts and save
5. Output trading signals (Trading Signal)

Usage:
    python main.py
"""

import os
import sys
import warnings
from datetime import datetime

# Windows terminal UTF-8 encoding support
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root directory is in Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Import project modules
from src import config
from src.data_loader import load_all_market_data, fetch_central_bank_text
from src.lng_economics import LNGCalculator
from src.macro_sentiment import MacroSentimentAnalyzer
from src.parameter_inventory import build_step1_inventory
from src.distribution_selection import build_step2_distribution_selection
from src.parameter_estimation import build_step3_parameter_estimates
from src.correlation_structure import build_step4_correlation_structure
from src.validation_calibration import build_step5_validation
from src.monte_carlo_spread import run_mc_spread, print_mc_summary
from src.swap_overlay import run_swap_overlay, print_swap_summary
from src import visualizer


def print_banner():
    """Print project banner"""
    banner = r"""
    ╔══════════════════════════════════════════════════════════════╗
    ║          🌊 Global LNG Arbitrage Monitor 🌊                ║
    ║          ─────────────────────────────────────              ║
    ║    US Gulf Coast → Europe / Asia Arbitrage Analysis         ║
    ║    NLP Macro Sentiment × Energy Trading Analytics           ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"    Runtime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"    Python:  {sys.version.split()[0]}")
    print()


def ensure_output_dir():
    """Ensure output directory exists"""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)


def run_market_data_pipeline():
    """
    Step 1: Market Data Loading Pipeline
    Download/load last 1 year of global natural gas and exchange rate data
    """
    print("\n" + "█" * 60)
    print("  STEP 1: Loading Market Data")
    print("█" * 60)
    
    market_data = load_all_market_data()
    return market_data


def run_step1_parameter_inventory(market_data):
    """
    Step 1b: Parameter Inventory and Modeling Priority Classification
    """
    print("\n" + "█" * 60)
    print("  STEP 1b: Netback Parameter Inventory")
    print("█" * 60)

    result = build_step1_inventory(market_data, output_dir=config.OUTPUT_DIR)
    inv = result["inventory_df"]

    print(f"\n  ✓ Step 1 inventory generated with {len(inv)} parameters")
    print(f"  ✓ CSV: {result['csv_path']}")
    print(f"  ✓ Markdown: {result['md_path']}")
    print(f"  ✓ Must-model set: {', '.join(result['priority_scope']['first_version_model'])}")
    return result


def run_step2_distribution_selection(
    market_data,
    current_charter_rate: float | None = None,
    current_fuel_cost: float | None = None,
):
    """
    Step 2: Distribution Family Selection for Uncertain Inputs

    Parameters
    ----------
    current_charter_rate : float or None
        Live market charter rate (USD/day), e.g. Spark25s spot.
        Falls back to config.DEFAULT_CHARTER_RATE.
    current_fuel_cost : float or None
        Live market fuel cost (USD/day), e.g. VLSFO bunker quote.
        Falls back to config.DEFAULT_FUEL_COST_PER_DAY.
    """
    print("\n" + "█" * 60)
    print("  STEP 2: Distribution Family Selection")
    print("█" * 60)

    result = build_step2_distribution_selection(
        market_data,
        output_dir=config.OUTPUT_DIR,
        horizon_days=(30, 60),
        current_charter_rate=current_charter_rate,
        current_fuel_cost=current_fuel_cost,
    )
    df = result["distribution_df"]

    print(f"\n  ✓ Step 2 distribution plan generated with {len(df)} parameter groups")
    print(f"  ✓ CSV: {result['csv_path']}")
    print(f"  ✓ Markdown: {result['md_path']}")
    print(f"  ✓ Horizon: {result['horizon_days'][0]}-{result['horizon_days'][1]} days")
    return result


def run_step3_parameter_estimation(
    market_data,
    current_charter_rate: float | None = None,
    current_fuel_cost: float | None = None,
    overrides: dict | None = None,
):
    """
    Step 3: Estimate Distribution Parameters for Monte Carlo Inputs

    Parameters
    ----------
    overrides : dict or None
        Trader manual overrides, keyed by parameter name, e.g.
        {"HH_Price": {"sigma": 0.50}, "Charter_Rate": {"s0": 85000}}
    """
    print("\n" + "█" * 60)
    print("  STEP 3: Parameter Estimation")
    print("█" * 60)

    result = build_step3_parameter_estimates(
        market_data,
        output_dir=config.OUTPUT_DIR,
        horizon_days=45,
        current_charter_rate=current_charter_rate,
        current_fuel_cost=current_fuel_cost,
        overrides=overrides,
    )

    print(f"\n  ✓ Estimated {len(result['estimates'])} parameter distributions")
    print(f"  ✓ Horizon: {result['estimates'][0].horizon_days} trading days")
    print(f"  ✓ CSV:  {result['csv_path']}")
    print(f"  ✓ JSON: {result['json_path']}")
    print(f"  ✓ MD:   {result['md_path']}")

    n_overridden = sum(1 for e in result["estimates"] if e.overridden_keys)
    if n_overridden:
        print(f"  ✓ Trader overrides applied to {n_overridden} parameter(s)")
    else:
        print("  ✓ No trader overrides (pure historical estimation)")

    for e in result["estimates"]:
        p = e.params
        tag = " [OVERRIDE]" if e.overridden_keys else ""
        if e.distribution_type == "ou":
            print(f"    {e.name:12s}  OU  S0={p['s0']:.2f}  theta={p['theta']:.2f}  "
                  f"T-range=[{p['horizon_p05']:.2f}, {p['horizon_p95']:.2f}]{tag}")
        elif e.distribution_type in ("lognormal", "gbm"):
            p05 = p.get("horizon_p05", p.get("p05", 0))
            p95 = p.get("horizon_p95", p.get("p95", 0))
            print(f"    {e.name:12s}  {e.distribution_type:5s}  S0={p['s0']:.2f}  "
                  f"T-range=[{p05:.2f}, {p95:.2f}]{tag}")
        elif e.distribution_type == "gamma":
            print(f"    {e.name:12s}  Gamma  mean_delay={p['mean_delay']:.1f}d{tag}")
        elif e.distribution_type == "triangular":
            print(f"    {e.name:12s}  Tri  [{p['low']:.4f}, {p['mode']:.4f}, {p['high']:.4f}]{tag}")

    return result


def run_step4_correlation_structure(market_data):
    """
    Step 4: Correlation Structure Estimation (Gaussian Copula)
    """
    print("\n" + "█" * 60)
    print("  STEP 4: Correlation Structure")
    print("█" * 60)

    result = build_step4_correlation_structure(
        market_data,
        output_dir=config.OUTPUT_DIR,
        n_demo_samples=5_000,
    )

    factors = result["factor_names"]
    corr = result["corr_matrix"]
    print(f"\n  ✓ {len(factors)} factors: {', '.join(factors)}")
    print(f"  ✓ Cholesky decomposition successful")
    print(f"  ✓ Demo copula sample: {result['demo_uniforms'].shape[0]:,} draws")
    print(f"  ✓ CSV:  {result['csv_path']}")
    print(f"  ✓ JSON: {result['json_path']}")
    print(f"  ✓ MD:   {result['md_path']}")

    print("\n  Correlation matrix:")
    for i, fi in enumerate(factors):
        vals = "  ".join(f"{corr.values[i,j]:+.2f}" for j in range(len(factors)))
        print(f"    {fi:14s}  {vals}")

    return result


def run_step5_validation(market_data, step3_result, step4_result):
    """
    Step 5: Validation & Calibration of Distribution Assumptions
    """
    print("\n" + "█" * 60)
    print("  STEP 5: Validation & Calibration")
    print("█" * 60)

    result = build_step5_validation(
        estimates=step3_result["estimates"],
        cholesky_L=step4_result["cholesky_L"],
        factor_names=step4_result["factor_names"],
        market_data=market_data,
        output_dir=config.OUTPUT_DIR,
        n_samples=10_000,
    )

    # ── A: Range checks ──
    print(f"\n  A. Range Check ({len(result['scenarios']):,} draws)")
    all_pass = True
    for r in result["range_checks"]:
        flag = "  " if r.status == "PASS" else ">>"
        print(f"    {flag} {r.parameter:14s}  P1={r.p01:>10.2f}  P99={r.p99:>10.2f}  [{r.bound_low:,.0f}, {r.bound_high:,.0f}]  {r.status}")
        if r.status != "PASS":
            all_pass = False
    if all_pass:
        print("    All range checks PASSED")

    # ── B: Coverage checks (rolling backtest) ──
    print(f"\n  B. Historical Coverage — Rolling Backtest (90% CI)")
    for c in result["coverage_checks"]:
        print(f"    {c.parameter:14s}  avg CI=[{c.avg_ci_low:.2f}, {c.avg_ci_high:.2f}]  "
              f"hit {c.coverage_pct:.1f}% of {c.n_windows} windows  {c.status}")

    # ── C: Extreme audit ──
    print(f"\n  C. Extreme Scenarios (5 lowest + 5 highest per factor)")
    for param, df in result["extremes"].items():
        lo = df[df["_extreme_type"] == "low"][param]
        hi = df[df["_extreme_type"] == "high"][param]
        if len(lo) and len(hi):
            print(f"    {param:14s}  worst_low={lo.iloc[0]:.2f}  worst_high={hi.iloc[-1]:.2f}")

    print(f"\n  ✓ CSV:  {result['csv_path']}")
    print(f"  ✓ MD:   {result['md_path']}")
    return result


def run_mc_spread_analysis(step5_result):
    """
    Step 6-MC: Monte Carlo Spread Distribution (Layer 2)
    Bridges Step 5 correlated scenarios into the Netback engine,
    producing spread/TCE distributions, JERA margin, Real Option
    valuation, and factor sensitivity analysis.
    """
    print("\n" + "█" * 60)
    print("  STEP 6-MC: Monte Carlo Spread Distribution")
    print("█" * 60)

    scenarios = step5_result["scenarios"]

    mc_output = run_mc_spread(
        scenarios=scenarios,
        output_dir=config.OUTPUT_DIR,
    )

    print_mc_summary(mc_output)

    return mc_output


def run_lng_economics(market_data):
    """
    Step 6 (original LNG Economics): LNG Economics Calculation
    - Calculate shipping costs for each route
    - Calculate Netback (netback value)
    - Determine arbitrage window status
    """
    print("\n" + "█" * 60)
    print("  STEP 6: LNG Economics Calculation")
    print("█" * 60)
    
    # Initialize calculator (using current market parameters)
    calc = LNGCalculator(
        charter_rate=config.DEFAULT_CHARTER_RATE,      # $60,000/day
        liquefaction_cost=config.DEFAULT_LIQUEFACTION_COST,  # $3.0/MMBtu
    )
    
    # Get latest prices
    latest = market_data.iloc[-1]
    hh_price = latest["HH_Price"]
    ttf_price = latest["TTF_Price"]
    jkm_price = latest["JKM_Price"]
    
    print(f"\n  📊 Latest Market Prices:")
    print(f"     Henry Hub:  ${hh_price:.2f}/MMBtu")
    print(f"     TTF:        ${ttf_price:.2f}/MMBtu")
    print(f"     JKM:        ${jkm_price:.2f}/MMBtu")
    
    # ---- Print voyage summary ----
    print("\n  🚢 Route Analysis:")
    calc.print_voyage_summary("US_Gulf_to_Rotterdam")
    calc.print_voyage_summary("US_Gulf_to_Tokyo_Panama")
    calc.print_voyage_summary("US_Gulf_to_Tokyo_COGH")
    
    # ---- Calculate Netback ----
    print("\n" + "=" * 60)
    print("  💰 Netback Analysis (Netback Value)")
    print("=" * 60)
    
    # Europe Netback
    nb_europe = calc.calculate_netback(
        destination_price=ttf_price,
        route_name="US_Gulf_to_Rotterdam",
        henry_hub_price=hh_price,
        destination_label="Europe (Rotterdam)",
    )
    
    # Asia Netback (via Panama Canal)
    nb_asia_panama = calc.calculate_netback(
        destination_price=jkm_price,
        route_name="US_Gulf_to_Tokyo_Panama",
        henry_hub_price=hh_price,
        destination_label="Asia (Tokyo via Panama)",
    )
    
    # Asia Netback (via Cape of Good Hope) - Additional reference
    nb_asia_cogh = calc.calculate_netback(
        destination_price=jkm_price,
        route_name="US_Gulf_to_Tokyo_COGH",
        henry_hub_price=hh_price,
        destination_label="Asia (Tokyo via Cape of Good Hope)",
    )
    
    # Print Netback results
    for nb in [nb_europe, nb_asia_panama, nb_asia_cogh]:
        print(f"\n  {'─' * 45}")
        print(f"  📍 {nb.destination}")
        print(f"  {'─' * 45}")
        print(f"  Destination Price: ${nb.destination_price:.2f}/MMBtu")
        print(f"  Shipping Cost:     ${nb.shipping_cost_per_mmbtu:.2f}/MMBtu")
        print(f"  Liquefaction Fee:  ${nb.liquefaction_cost:.2f}/MMBtu")
        print(f"  Netback:           ${nb.netback:.2f}/MMBtu")
        print(f"  Henry Hub:         ${nb.henry_hub_price:.2f}/MMBtu")
        print(f"  Arbitrage Spread:  ${nb.arbitrage_spread:+.2f}/MMBtu")
        print(f"  Signal:            {nb.signal}")
    
    # ---- Calculate historical Netback series ----
    hist_nb_europe = calc.calculate_historical_netback(
        market_data, "US_Gulf_to_Rotterdam", "TTF_Price"
    )
    hist_nb_asia = calc.calculate_historical_netback(
        market_data, "US_Gulf_to_Tokyo_Panama", "JKM_Price"
    )
    
    return {
        "calculator": calc,
        "nb_europe": nb_europe,
        "nb_asia_panama": nb_asia_panama,
        "nb_asia_cogh": nb_asia_cogh,
        "hist_europe": hist_nb_europe,
        "hist_asia": hist_nb_asia,
    }


def run_nlp_analysis(market_data):
    """
    Step 5: NLP Macro Sentiment Analysis
    - Analyze Fed/BOJ meeting minutes text
    - Calculate hawk/dove tendency
    - Assess impact on USD/JPY
    """
    print("\n" + "█" * 60)
    print("  STEP 6: NLP Macro Sentiment Analysis")
    print("█" * 60)
    
    # Fetch central bank text
    texts = fetch_central_bank_text(source="sample")
    
    # Initialize analyzer
    analyzer = MacroSentimentAnalyzer()
    
    # Batch analysis
    results = analyzer.analyze_multiple(texts)
    
    # Generate and print report
    report = analyzer.generate_sentiment_report(results)
    print(report)
    
    # Calculate sentiment-exchange rate correlation
    fx_data = market_data[["USD_JPY"]].copy()
    sentiment_scores = {
        "fed": results["fed"]["net_hawk_dove"],
        "boj": results["boj"]["net_hawk_dove"],
    }
    
    fx_corr = analyzer.compute_sentiment_fx_correlation(
        sentiment_scores, fx_data, window=20
    )
    
    return {
        "analyzer": analyzer,
        "results": results,
        "fx_correlation": fx_corr,
        "sentiment_scores": sentiment_scores,
    }


def run_swap_overlay_step(mc_output):
    """
    Step 6-SW: Financial Swap / FFA Overlay on Optimal Spread Distribution.
    Applies HH + JKM price swaps (and optionally Charter FFA) on top of the
    physical spread distribution.  Zero-invasive: reads mc_output, produces
    a HedgedOutput with full effectiveness metrics.
    """
    print("\n" + "█" * 60)
    print("  STEP 6-SW: Swap Overlay (Hedge Analysis)")
    print("█" * 60)

    hedged_output = run_swap_overlay(
        mc_output=mc_output,
        output_dir=config.OUTPUT_DIR,
    )

    print_swap_summary(hedged_output)
    return hedged_output


def generate_charts(market_data, lng_results, nlp_results, mc_output=None,
                    hedged_output=None):
    """
    Step 7: Generate Professional Charts (01–04 classic, 05–07 MC, 08 Swap)
    """
    print("\n" + "█" * 60)
    print("  STEP 7: Generating Visualization Charts")
    print("█" * 60)
    
    # Chart 1: Global natural gas spreads
    print("\n  📈 Generating Chart 1: Global Gas Spreads...")
    visualizer.plot_global_gas_spreads(
        market_data,
        save_path=os.path.join(config.OUTPUT_DIR, "01_global_gas_spreads.png"),
    )
    
    # Chart 2: Arbitrage window (Netback)
    print("  📊 Generating Chart 2: Arbitrage Window (Netback)...")
    visualizer.plot_arbitrage_netback(
        netback_europe=lng_results["nb_europe"],
        netback_asia=lng_results["nb_asia_panama"],
        save_path=os.path.join(config.OUTPUT_DIR, "02_arbitrage_netback.png"),
    )
    
    # Chart 3: Macro sentiment impact
    print("  🧠 Generating Chart 3: Macro Sentiment Impact...")
    visualizer.plot_macro_sentiment_impact(
        sentiment_results=nlp_results["results"],
        fx_correlation_data=nlp_results["fx_correlation"],
        save_path=os.path.join(config.OUTPUT_DIR, "03_macro_sentiment.png"),
    )
    
    # Chart 4: Historical Netback
    print("  📉 Generating Chart 4: Historical Netback...")
    visualizer.plot_historical_netback(
        netback_data_europe=lng_results["hist_europe"],
        netback_data_asia=lng_results["hist_asia"],
        market_data=market_data,
        save_path=os.path.join(config.OUTPUT_DIR, "04_historical_netback.png"),
    )
    
    # Charts 5–7: Monte Carlo Distribution Analysis
    if mc_output is not None:
        print("  📊 Generating Chart 5: MC Spread Distribution...")
        visualizer.plot_mc_spread_distribution(
            mc_output,
            save_path=os.path.join(config.OUTPUT_DIR, "05_mc_spread_distribution.png"),
        )
        
        print("  📊 Generating Chart 6: MC TCE Comparison...")
        visualizer.plot_mc_tce_comparison(
            mc_output,
            save_path=os.path.join(config.OUTPUT_DIR, "06_mc_tce_comparison.png"),
        )
        
        print("  📊 Generating Chart 7: MC Sensitivity Tornado...")
        visualizer.plot_mc_sensitivity_tornado(
            mc_output,
            save_path=os.path.join(config.OUTPUT_DIR, "07_mc_sensitivity_tornado.png"),
        )

    # Chart 8: Swap Overlay — Hedged vs Unhedged Distribution
    if hedged_output is not None:
        print("  📊 Generating Chart 8: Swap Hedge Overlay...")
        visualizer.plot_hedge_overlay(
            hedged_output,
            save_path=os.path.join(config.OUTPUT_DIR, "08_swap_hedge_overlay.png"),
        )

    # Close all figure windows to avoid memory leaks
    import matplotlib.pyplot as plt
    plt.close("all")
    
    print("\n  ✓ All charts saved to data/ directory")


def print_trading_signal(lng_results, nlp_results):
    """
    Step 7: Output Trading Signal
    Integrate LNG arbitrage analysis and macro sentiment to provide recommendations.
    """
    print("\n" + "█" * 60)
    print("  STEP 8: Trading Signal (TRADING SIGNAL)")
    print("█" * 60)
    
    nb_eu = lng_results["nb_europe"]
    nb_asia = lng_results["nb_asia_panama"]
    nb_asia_cogh = lng_results["nb_asia_cogh"]
    
    fed_score = nlp_results["sentiment_scores"]["fed"]
    boj_score = nlp_results["sentiment_scores"]["boj"]
    
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                  📋 TRADING SIGNAL SUMMARY                  ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  [LNG Arbitrage]                                            ║
    ║  ├─ Europe Netback:    ${nb_eu.netback:>6.2f}/MMBtu  (Spread: ${nb_eu.arbitrage_spread:+.2f}) ║
    ║  ├─ Asia (Panama):     ${nb_asia.netback:>6.2f}/MMBtu  (Spread: ${nb_asia.arbitrage_spread:+.2f}) ║
    ║  └─ Asia (COGH):       ${nb_asia_cogh.netback:>6.2f}/MMBtu  (Spread: ${nb_asia_cogh.arbitrage_spread:+.2f}) ║
    ║                                                              ║
    ║  [Macro Sentiment]                                          ║
    ║  ├─ Fed Stance:  {nlp_results['results']['fed']['stance']:<20s}             ║
    ║  ├─ BOJ Stance:  {nlp_results['results']['boj']['stance']:<20s}             ║
    ║  └─ USD/JPY Bias: {'Bullish USD 📈' if fed_score > boj_score else 'Bearish USD 📉':<20s}             ║
    ║                                                              ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║""")
    
    # Comprehensive recommendation
    best_dest = None
    best_spread = -float("inf")
    
    for label, nb in [("Europe", nb_eu), ("Asia (Panama)", nb_asia), ("Asia (COGH)", nb_asia_cogh)]:
        if nb.arbitrage_spread > best_spread:
            best_spread = nb.arbitrage_spread
            best_dest = label
    
    if best_spread > 1.0:
        action = f"STRONG BUY: Suggest Cargo Diversion to {best_dest}"
        emoji = "🟢"
    elif best_spread > 0:
        action = f"MARGINAL: Small Arb Window to {best_dest}, proceed with caution"
        emoji = "🟡"
    else:
        action = "NO ACTION: All Arb Windows Closed, hold position"
        emoji = "🔴"
    
    print(f"    ║  {emoji} RECOMMENDATION:                                       ║")
    print(f"    ║  {action:<58s} ║")
    print(f"    ║                                                              ║")
    
    # Exchange rate risk warning
    if abs(fed_score - boj_score) > 0.3:
        fx_note = "⚠️  FX Risk: Significant policy divergence detected"
    else:
        fx_note = "✅ FX Risk: Policy divergence is moderate"
    
    print(f"    ║  {fx_note:<58s} ║")
    print(f"    ║                                                              ║")
    print(f"    ╚══════════════════════════════════════════════════════════════╝")
    print()


def print_probabilistic_trading_signal(mc_output, nlp_results):
    """
    Step 8b: Probabilistic Trading Signal (upgraded from single-point).
    Uses MC spread distributions to produce confidence-weighted recommendations.
    """
    import numpy as np

    print("\n" + "█" * 60)
    print("  STEP 8b: Probabilistic Trading Signal (MC-Enhanced)")
    print("█" * 60)

    opt = mc_output.optimal_strategy
    s_opt = opt.stats_optimal_spread
    jera = mc_output.jera_margin

    fed_score = nlp_results["sentiment_scores"]["fed"]
    boj_score = nlp_results["sentiment_scores"]["boj"]

    # ── Per-route summary ──
    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║           📋 PROBABILISTIC TRADING SIGNAL (N={mc_output.n_scenarios:,})        ║
    ╠══════════════════════════════════════════════════════════════╣
    ║                                                              ║
    ║  [Spread Distribution — $/MMBtu]                            ║""")

    for rr in mc_output.route_results:
        s = rr.stats_spread
        t = rr.stats_tce
        label = rr.route.label
        print(f"    ║  {label:<30s}                            ║")
        print(f"    ║    Spread  P50=${s.median:+.2f}  "
              f"[P5=${s.p05:+.2f}, P95=${s.p95:+.2f}]          ║")
        print(f"    ║    TCE     ${t.mean:>+,.0f}/day   "
              f"P(arb>0)={s.prob_positive:.0%}  "
              f"P(arb>$1)={s.prob_above_1:.0%}       ║")

    print(f"    ║                                                              ║")

    # ── Optimal strategy ──
    print(f"    ║  [Optimal Strategy — Destination Flexibility]              ║")
    print(f"    ║    P50=${s_opt.median:+.2f}  "
          f"P(profit)={s_opt.prob_positive:.0%}  "
          f"VaR5%=${s_opt.var_5pct:+.2f}  "
          f"CVaR5%=${s_opt.cvar_5pct:+.2f}   ║")
    print(f"    ║    Option Premium: "
          f"${opt.option_premium_spread:+.4f}/MMBtu  "
          f"(${opt.option_premium_tce:+,.0f}/day)        ║")
    print(f"    ║                                                              ║")

    # ── Route selection ──
    print(f"    ║  [Route Selection Probability]                             ║")
    for label, prob in opt.route_selection_prob.items():
        bar = "█" * int(prob * 30)
        print(f"    ║    {label:<22s} {prob:5.1%}  {bar:<30s} ║")

    print(f"    ║                                                              ║")

    # ── JERA ──
    mean_profit = float(np.mean(jera.domestic_profit_jpy))
    print(f"    ║  [JERA Domestic Margin]                                    ║")
    print(f"    ║    Mean profit: {mean_profit:+,.0f} JPY/MMBtu  "
          f"Divert prob: {jera.divert_probability:.1%}         ║")
    print(f"    ║                                                              ║")

    # ── Macro overlay ──
    print(f"    ║  [Macro Sentiment]                                          ║")
    print(f"    ║    Fed: {nlp_results['results']['fed']['stance']:<14s}  "
          f"BOJ: {nlp_results['results']['boj']['stance']:<14s}            ║")
    fx_bias = "Bullish USD" if fed_score > boj_score else "Bearish USD"
    print(f"    ║    USD/JPY Bias: {fx_bias:<14s}                              ║")
    print(f"    ║                                                              ║")
    print(f"    ╠══════════════════════════════════════════════════════════════╣")
    print(f"    ║                                                              ║")

    # ── Probabilistic recommendation ──
    prob_pos = s_opt.prob_positive
    median_spread = s_opt.median

    if prob_pos > 0.80 and median_spread > 1.0:
        emoji = "🟢"
        action = "HIGH CONFIDENCE BUY"
        detail = (f"P(profit)={prob_pos:.0%}, "
                  f"median=${median_spread:+.2f}/MMBtu")
    elif prob_pos > 0.60:
        emoji = "🟡"
        action = "MODERATE — positive EV but tail risk exists"
        detail = (f"P(profit)={prob_pos:.0%}, "
                  f"VaR5%=${s_opt.var_5pct:+.2f}")
    elif prob_pos > 0.40:
        emoji = "🟠"
        action = "CAUTIOUS — near break-even, monitor closely"
        detail = (f"P(profit)={prob_pos:.0%}, "
                  f"CVaR5%=${s_opt.cvar_5pct:+.2f}")
    else:
        emoji = "🔴"
        action = "AVOID — majority of scenarios unprofitable"
        detail = (f"P(profit)={prob_pos:.0%}, "
                  f"median=${median_spread:+.2f}/MMBtu")

    print(f"    ║  {emoji} {action:<57s} ║")
    print(f"    ║    {detail:<58s} ║")
    print(f"    ║                                                              ║")

    # FX risk overlay
    if abs(fed_score - boj_score) > 0.3:
        fx_note = "FX Risk: Significant policy divergence detected"
        fx_icon = "⚠️ "
    else:
        fx_note = "FX Risk: Policy divergence is moderate"
        fx_icon = "✅"
    print(f"    ║  {fx_icon} {fx_note:<57s} ║")

    if jera.divert_probability > 0.3:
        jera_note = (f"JERA Alert: {jera.divert_probability:.0%} "
                     f"divert probability — JKM demand at risk")
        print(f"    ║  ⚠️  {jera_note:<56s} ║")

    print(f"    ║                                                              ║")
    print(f"    ╚══════════════════════════════════════════════════════════════╝")
    print()


def main():
    """Main program entry"""
    try:
        # Banner
        print_banner()
        
        # Ensure output directory
        ensure_output_dir()
        
        # Step 1-5: Market data → parameter modeling → validation
        market_data = run_market_data_pipeline()
        run_step1_parameter_inventory(market_data)
        run_step2_distribution_selection(market_data)
        step3_result = run_step3_parameter_estimation(market_data)
        step4_result = run_step4_correlation_structure(market_data)
        step5_result = run_step5_validation(market_data, step3_result, step4_result)
        
        # Step 6-MC: Monte Carlo Spread Distribution (Layer 2)
        mc_output = run_mc_spread_analysis(step5_result)

        # Step 6-SW: Swap / FFA overlay on optimal spread distribution
        hedged_output = run_swap_overlay_step(mc_output)

        # Step 6: Single-point LNG economics (reference baseline)
        lng_results = run_lng_economics(market_data)

        # Step 6: NLP macro sentiment analysis
        nlp_results = run_nlp_analysis(market_data)

        # Step 7: Generate charts (including MC + Swap overlay charts)
        generate_charts(market_data, lng_results, nlp_results, mc_output,
                        hedged_output)

        # Step 8: Output trading signals
        print_trading_signal(lng_results, nlp_results)
        print_probabilistic_trading_signal(mc_output, nlp_results)
        
        print("=" * 60)
        print("  ✅ Global LNG Arbitrage Monitor completed!")
        print(f"  📁 Charts and data saved to: {os.path.abspath(config.OUTPUT_DIR)}/")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n  ⚠ User interrupted, program exiting.")
    except Exception as e:
        print(f"\n  ❌ Runtime error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
