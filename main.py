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


def run_lng_economics(market_data):
    """
    Step 3: LNG Economics Calculation
    - Calculate shipping costs for each route
    - Calculate Netback (netback value)
    - Determine arbitrage window status
    """
    print("\n" + "█" * 60)
    print("  STEP 3: LNG Economics Calculation")
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
    Step 4: NLP Macro Sentiment Analysis
    - Analyze Fed/BOJ meeting minutes text
    - Calculate hawk/dove tendency
    - Assess impact on USD/JPY
    """
    print("\n" + "█" * 60)
    print("  STEP 4: NLP Macro Sentiment Analysis")
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


def generate_charts(market_data, lng_results, nlp_results):
    """
    Step 5: Generate Professional Charts
    """
    print("\n" + "█" * 60)
    print("  STEP 5: Generating Visualization Charts")
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
    
    # Additional chart: Historical Netback
    print("  📉 Generating Additional Chart: Historical Netback...")
    visualizer.plot_historical_netback(
        netback_data_europe=lng_results["hist_europe"],
        netback_data_asia=lng_results["hist_asia"],
        market_data=market_data,
        save_path=os.path.join(config.OUTPUT_DIR, "04_historical_netback.png"),
    )
    
    # Close all figure windows to avoid memory leaks
    import matplotlib.pyplot as plt
    plt.close("all")
    
    print("\n  ✓ All charts saved to data/ directory")


def print_trading_signal(lng_results, nlp_results):
    """
    Step 6: Output Trading Signal
    Integrate LNG arbitrage analysis and macro sentiment to provide recommendations.
    """
    print("\n" + "█" * 60)
    print("  STEP 6: Trading Signal (TRADING SIGNAL)")
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


def main():
    """Main program entry"""
    try:
        # Banner
        print_banner()
        
        # Ensure output directory
        ensure_output_dir()
        
        # Step 1: Load market data
        market_data = run_market_data_pipeline()
        run_step1_parameter_inventory(market_data)
        run_step2_distribution_selection(market_data)
        
        # Step 3: LNG economics calculation
        lng_results = run_lng_economics(market_data)
        
        # Step 4: NLP macro sentiment analysis
        nlp_results = run_nlp_analysis(market_data)
        
        # Step 5: Generate charts
        generate_charts(market_data, lng_results, nlp_results)
        
        # Step 6: Output trading signal
        print_trading_signal(lng_results, nlp_results)
        
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
