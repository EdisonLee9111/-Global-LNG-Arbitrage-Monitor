"""
visualizer.py - Professional Visualization Module
==================================================
Charts 01–04: Market data & single-point Netback analysis
Charts 05–07: Monte Carlo distribution analysis (Layer 2)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, Optional
from scipy import stats
import os

from . import config
from .monte_carlo_spread import MCSpreadOutput


# Set global plotting style
plt.rcParams.update({
    "figure.facecolor": "#f8f9fa",
    "axes.facecolor": "#ffffff",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 11,
    "axes.labelsize": 12,
    "axes.titlesize": 14,
    "legend.fontsize": 10,
})

# Custom color palette (energy industry style)
COLORS = {
    "henry_hub": "#2196F3",     # Blue (US gas)
    "ttf": "#FF9800",           # Orange (European gas)
    "jkm": "#E91E63",           # Pink (Asian gas)
    "netback_europe": "#4CAF50",  # Green
    "netback_asia": "#9C27B0",    # Purple
    "arb_open": "#4CAF50",        # Green (arbitrage open)
    "arb_closed": "#F44336",      # Red (arbitrage closed)
    "scatter": "#3F51B5",         # Indigo
    "regression": "#E91E63",      # Regression line
    # MC chart palette
    "mc_eu": "#4CAF50",           # Green  — Europe
    "mc_asia_panama": "#9C27B0",  # Purple — Asia (Panama)
    "mc_asia_cogh": "#607D8B",    # Blue-gray — Asia (COGH)
    "mc_optimal": "#FF6F00",      # Amber  — Optimal strategy
    "mc_nogo": "#BDBDBD",         # Gray   — No-Go
    "mc_positive": "#1B5E20",     # Dark green — positive correlation
    "mc_negative": "#B71C1C",     # Dark red   — negative correlation
}


def plot_global_gas_spreads(
    market_data: pd.DataFrame,
    save_path: str = None,
) -> plt.Figure:
    """
    Chart 1: Global Gas Spreads - Global Natural Gas Price Trends
    
    Displays historical price trends of Henry Hub, TTF, JKM on one chart,
    intuitively showing spread changes between regions.
    
    Parameters
    ----------
    market_data : pd.DataFrame
        Must contain HH_Price, TTF_Price, JKM_Price columns
    save_path : str, optional
        Image save path
        
    Returns
    -------
    matplotlib.Figure
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[3, 1])
    fig.suptitle("Global Natural Gas / LNG Price Spreads", fontsize=16, fontweight="bold", y=0.98)
    
    # ---- Top chart: Price trends ----
    ax1 = axes[0]
    
    ax1.plot(market_data.index, market_data["HH_Price"], 
             color=COLORS["henry_hub"], linewidth=2, label="Henry Hub (US)", alpha=0.9)
    ax1.plot(market_data.index, market_data["TTF_Price"], 
             color=COLORS["ttf"], linewidth=2, label="TTF (Europe)", alpha=0.9)
    ax1.plot(market_data.index, market_data["JKM_Price"], 
             color=COLORS["jkm"], linewidth=2, label="JKM (Asia)", alpha=0.9)
    
    # Fill HH-JKM spread area
    ax1.fill_between(
        market_data.index,
        market_data["HH_Price"],
        market_data["JKM_Price"],
        alpha=0.1, color=COLORS["jkm"],
        label="HH-JKM Spread"
    )
    
    ax1.set_ylabel("Price ($/MMBtu)")
    ax1.legend(loc="upper left", framealpha=0.9)
    ax1.set_title("Price Comparison: Henry Hub vs TTF vs JKM")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    
    # Annotate latest prices
    latest = market_data.iloc[-1]
    ax1.annotate(
        f'HH: ${latest["HH_Price"]:.2f}',
        xy=(market_data.index[-1], latest["HH_Price"]),
        xytext=(10, 0), textcoords="offset points",
        fontsize=9, color=COLORS["henry_hub"], fontweight="bold"
    )
    ax1.annotate(
        f'TTF: ${latest["TTF_Price"]:.2f}',
        xy=(market_data.index[-1], latest["TTF_Price"]),
        xytext=(10, 0), textcoords="offset points",
        fontsize=9, color=COLORS["ttf"], fontweight="bold"
    )
    ax1.annotate(
        f'JKM: ${latest["JKM_Price"]:.2f}',
        xy=(market_data.index[-1], latest["JKM_Price"]),
        xytext=(10, -15), textcoords="offset points",
        fontsize=9, color=COLORS["jkm"], fontweight="bold"
    )
    
    # ---- Bottom chart: Spreads ----
    ax2 = axes[1]
    
    spread_ttf_hh = market_data["TTF_Price"] - market_data["HH_Price"]
    spread_jkm_hh = market_data["JKM_Price"] - market_data["HH_Price"]
    
    ax2.plot(market_data.index, spread_ttf_hh, 
             color=COLORS["ttf"], linewidth=1.5, label="TTF - HH", alpha=0.8)
    ax2.plot(market_data.index, spread_jkm_hh, 
             color=COLORS["jkm"], linewidth=1.5, label="JKM - HH", alpha=0.8)
    ax2.axhline(y=0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    
    ax2.fill_between(market_data.index, 0, spread_jkm_hh,
                     where=(spread_jkm_hh > 0), alpha=0.15, color=COLORS["arb_open"])
    ax2.fill_between(market_data.index, 0, spread_jkm_hh,
                     where=(spread_jkm_hh <= 0), alpha=0.15, color=COLORS["arb_closed"])
    
    ax2.set_ylabel("Spread ($/MMBtu)")
    ax2.set_xlabel("Date")
    ax2.legend(loc="upper left", framealpha=0.9)
    ax2.set_title("Price Spreads vs Henry Hub")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    
    return fig


def plot_arbitrage_netback(
    netback_europe,   # NetbackResult
    netback_asia,     # NetbackResult
    save_path: str = None,
) -> plt.Figure:
    """
    Chart 2: Arbitrage Window (Netback) - Arbitrage Window Comparison
    
    Bar chart comparison:
    - US → Europe Netback vs Henry Hub
    - US → Asia (via Panama) Netback vs Henry Hub
    Instantly see which destination is more profitable.
    
    Parameters
    ----------
    netback_europe : NetbackResult
        European route Netback result
    netback_asia : NetbackResult
        Asian route Netback result
    save_path : str, optional
        Image save path
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    fig.suptitle("LNG Arbitrage Window Analysis: US Gulf Coast Exports",
                 fontsize=15, fontweight="bold", y=1.02)
    
    # ---- Left chart: Netback comparison bar chart ----
    ax1 = axes[0]
    
    categories = ["Europe\n(Rotterdam)", "Asia\n(Tokyo via Panama)"]
    netbacks = [netback_europe.netback, netback_asia.netback]
    hh_price = netback_europe.henry_hub_price  # Both are the same
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars_nb = ax1.bar(x - width/2, netbacks, width, 
                      label="Netback ($/MMBtu)",
                      color=[COLORS["netback_europe"], COLORS["netback_asia"]],
                      edgecolor="white", linewidth=1.5)
    bars_hh = ax1.bar(x + width/2, [hh_price, hh_price], width,
                      label=f"Henry Hub (${hh_price:.2f})",
                      color=COLORS["henry_hub"], alpha=0.7,
                      edgecolor="white", linewidth=1.5)
    
    # Annotate values
    for bar in bars_nb:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                f'${height:.2f}', ha='center', va='bottom', fontweight='bold', fontsize=11)
    for bar in bars_hh:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                f'${height:.2f}', ha='center', va='bottom', fontsize=10, color="gray")
    
    ax1.set_ylabel("Price ($/MMBtu)")
    ax1.set_title("Netback vs Henry Hub")
    ax1.set_xticks(x)
    ax1.set_xticklabels(categories)
    ax1.legend()
    ax1.set_ylim(0, max(netbacks + [hh_price]) * 1.3)
    
    # ---- Right chart: Arbitrage spread (Arb Spread) ----
    ax2 = axes[1]
    
    spreads = [netback_europe.arbitrage_spread, netback_asia.arbitrage_spread]
    bar_colors = [
        COLORS["arb_open"] if s > 0 else COLORS["arb_closed"] for s in spreads
    ]
    
    bars = ax2.bar(categories, spreads, color=bar_colors, 
                   edgecolor="white", linewidth=1.5, width=0.5)
    
    ax2.axhline(y=0, color="black", linewidth=1, linestyle="--")
    
    # Annotate values and status
    for i, (bar, spread) in enumerate(zip(bars, spreads)):
        height = bar.get_height()
        label = "OPEN ✓" if spread > 0 else "CLOSED ✗"
        va = 'bottom' if height >= 0 else 'top'
        offset = 0.05 if height >= 0 else -0.05
        ax2.text(bar.get_x() + bar.get_width()/2., height + offset,
                f'${spread:+.2f}\n({label})', 
                ha='center', va=va, fontweight='bold', fontsize=11)
    
    ax2.set_ylabel("Arbitrage Spread ($/MMBtu)")
    ax2.set_title("Arbitrage Window Status")
    
    # Add cost breakdown text box
    info_text = (
        f"Assumptions:\n"
        f"  Charter Rate: ${netback_europe.shipping_cost_per_mmbtu:.2f}/MMBtu (Europe)\n"
        f"  Charter Rate: ${netback_asia.shipping_cost_per_mmbtu:.2f}/MMBtu (Asia)\n"
        f"  Liquefaction: ${netback_europe.liquefaction_cost:.2f}/MMBtu\n"
        f"  Boil-off Rate: {config.BOIL_OFF_RATE*100:.2f}%/day"
    )
    ax2.text(0.02, 0.98, info_text, transform=ax2.transAxes,
             fontsize=8, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    
    return fig


def plot_macro_sentiment_impact(
    sentiment_results: Dict,
    fx_correlation_data: pd.DataFrame = None,
    save_path: str = None,
) -> plt.Figure:
    """
    Chart 3: Macro Impact - Relationship between Central Bank Sentiment and Exchange Rate Volatility
    
    Contains:
    - Scatter plot: Fed Sentiment Score vs USD/JPY Volatility
    - Regression line
    - Sentiment score radar chart / bar chart
    
    Parameters
    ----------
    sentiment_results : dict
        NLP analysis results
    fx_correlation_data : pd.DataFrame, optional
        Exchange rate-sentiment correlation data
    save_path : str
        Save path
    """
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle("Macro Sentiment Impact on USD/JPY", fontsize=15, fontweight="bold")
    
    # ---- Left chart: Scatter plot + Regression line ----
    ax1 = axes[0]
    
    if fx_correlation_data is not None and len(fx_correlation_data) > 10:
        x_data = fx_correlation_data["Sentiment_Dynamic"].values
        y_data = fx_correlation_data["FX_Volatility"].values
        
        # Remove NaN
        mask = ~(np.isnan(x_data) | np.isnan(y_data))
        x_clean = x_data[mask]
        y_clean = y_data[mask]
        
        if len(x_clean) > 5:
            ax1.scatter(x_clean, y_clean, alpha=0.4, s=20, 
                       color=COLORS["scatter"], edgecolors="white", linewidth=0.5)
            
            # Linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)
            x_line = np.linspace(x_clean.min(), x_clean.max(), 100)
            y_line = slope * x_line + intercept
            ax1.plot(x_line, y_line, color=COLORS["regression"], 
                    linewidth=2, linestyle="--", label=f"OLS (R²={r_value**2:.3f})")
            
            ax1.set_xlabel("Sentiment Index (Hawk-Dove)")
            ax1.set_ylabel("USD/JPY Annualized Volatility")
            ax1.legend()
            ax1.set_title("Sentiment vs FX Volatility")
            
            # R² and p-value annotation
            ax1.text(0.05, 0.95, 
                    f"R² = {r_value**2:.4f}\np-value = {p_value:.4f}\nSlope = {slope:.4f}",
                    transform=ax1.transAxes, fontsize=9, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    else:
        # Fallback: Use simulated data for demonstration
        np.random.seed(42)
        n_points = 100
        x_sim = np.random.normal(0, 0.3, n_points)
        y_sim = 0.08 + 0.05 * x_sim + np.random.normal(0, 0.02, n_points)
        
        ax1.scatter(x_sim, y_sim, alpha=0.5, s=25,
                   color=COLORS["scatter"], edgecolors="white", linewidth=0.5)
        
        slope, intercept, r_value, p_value, _ = stats.linregress(x_sim, y_sim)
        x_line = np.linspace(x_sim.min(), x_sim.max(), 100)
        ax1.plot(x_line, slope * x_line + intercept, 
                color=COLORS["regression"], linewidth=2, linestyle="--",
                label=f"OLS (R²={r_value**2:.3f})")
        
        ax1.set_xlabel("Fed Sentiment Score (simulated)")
        ax1.set_ylabel("USD/JPY Volatility (simulated)")
        ax1.legend()
        ax1.set_title("Sentiment vs FX Volatility (Simulated)")
    
    # ---- Right chart: Sentiment score comparison bar chart ----
    ax2 = axes[1]
    
    if sentiment_results:
        labels_list = []
        hawk_scores = []
        dove_scores = []
        net_scores = []
        
        for key, res in sentiment_results.items():
            labels_list.append(res.get("label", key.upper()))
            hawk_scores.append(res.get("hawkish_score", 0))
            dove_scores.append(res.get("dovish_score", 0))
            net_scores.append(res.get("net_hawk_dove", 0))
        
        x = np.arange(len(labels_list))
        width = 0.25
        
        ax2.bar(x - width, hawk_scores, width, label="Hawkish 🦅", 
                color="#E53935", alpha=0.8)
        ax2.bar(x, dove_scores, width, label="Dovish 🕊️", 
                color="#1E88E5", alpha=0.8)
        ax2.bar(x + width, [abs(n) for n in net_scores], width, 
                label="Net |H-D|",
                color=["#E53935" if n > 0 else "#1E88E5" for n in net_scores], 
                alpha=0.5, edgecolor="black", linewidth=1)
        
        # Annotate net scores
        for i, net in enumerate(net_scores):
            ax2.text(i + width, abs(net) + 0.02, 
                    f"{net:+.2f}", ha='center', fontsize=10, fontweight="bold")
        
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels_list)
        ax2.set_ylabel("Score")
        ax2.set_title("Central Bank Hawk-Dove Scores")
        ax2.legend(loc="upper right")
        ax2.set_ylim(0, 1.1)
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    
    return fig


def plot_historical_netback(
    netback_data_europe: pd.DataFrame,
    netback_data_asia: pd.DataFrame,
    market_data: pd.DataFrame,
    save_path: str = None,
) -> plt.Figure:
    """
    Additional Chart: Historical Netback Time Series
    
    Shows historical arbitrage window open/close status changes.
    """
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.suptitle("Historical Netback & Arbitrage Window", fontsize=15, fontweight="bold")
    
    # ---- Top chart: Netback vs HH Price ----
    ax1 = axes[0]
    ax1.plot(market_data.index, market_data["HH_Price"],
             color=COLORS["henry_hub"], linewidth=2, label="Henry Hub", alpha=0.9)
    ax1.plot(netback_data_europe.index, netback_data_europe["Netback"],
             color=COLORS["netback_europe"], linewidth=1.5, label="Netback (Europe)", alpha=0.8)
    ax1.plot(netback_data_asia.index, netback_data_asia["Netback"],
             color=COLORS["netback_asia"], linewidth=1.5, label="Netback (Asia)", alpha=0.8)
    
    ax1.set_ylabel("$/MMBtu")
    ax1.legend(loc="upper left")
    ax1.set_title("Netback Values vs Henry Hub Price")
    
    # ---- Bottom chart: Arb Spread ----
    ax2 = axes[1]
    ax2.fill_between(netback_data_europe.index, 0, netback_data_europe["Arb_Spread"],
                     where=(netback_data_europe["Arb_Spread"] > 0),
                     alpha=0.3, color=COLORS["netback_europe"], label="Europe Arb (Open)")
    ax2.fill_between(netback_data_asia.index, 0, netback_data_asia["Arb_Spread"],
                     where=(netback_data_asia["Arb_Spread"] > 0),
                     alpha=0.3, color=COLORS["netback_asia"], label="Asia Arb (Open)")
    
    ax2.plot(netback_data_europe.index, netback_data_europe["Arb_Spread"],
             color=COLORS["netback_europe"], linewidth=1, alpha=0.7)
    ax2.plot(netback_data_asia.index, netback_data_asia["Arb_Spread"],
             color=COLORS["netback_asia"], linewidth=1, alpha=0.7)
    
    ax2.axhline(y=0, color="black", linewidth=1, linestyle="--")
    ax2.set_ylabel("Arb Spread ($/MMBtu)")
    ax2.set_xlabel("Date")
    ax2.legend(loc="upper left")
    ax2.set_title("Arbitrage Spread (Positive = Open Window)")
    
    plt.tight_layout()
    
    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    
    return fig


# =========================================================================
# Charts 05–07: Monte Carlo Distribution Analysis
# =========================================================================

_ROUTE_COLORS = [
    COLORS["mc_eu"],
    COLORS["mc_asia_panama"],
    COLORS["mc_asia_cogh"],
]


def plot_mc_spread_distribution(
    mc_output: MCSpreadOutput,
    save_path: str = None,
) -> plt.Figure:
    """
    Chart 05: Spread probability distributions for all routes + Optimal,
    with route-selection breakdown and option premium annotation.
    """
    fig = plt.figure(figsize=(16, 9))
    gs = fig.add_gridspec(2, 2, width_ratios=[3, 1], height_ratios=[3, 1],
                          hspace=0.30, wspace=0.25)
    fig.suptitle(
        f"Monte Carlo Spread Distribution  (N = {mc_output.n_scenarios:,})",
        fontsize=16, fontweight="bold", y=0.98,
    )

    # ── Main panel: KDE overlay ──
    ax_kde = fig.add_subplot(gs[0, 0])
    route_results = mc_output.route_results
    opt = mc_output.optimal_strategy

    x_all = np.concatenate([rr.spread for rr in route_results])
    x_lo = min(x_all.min(), 0) - 0.5
    x_hi = x_all.max() + 0.5
    x_grid = np.linspace(x_lo, x_hi, 500)

    for rr, color in zip(route_results, _ROUTE_COLORS):
        kde = stats.gaussian_kde(rr.spread)
        y = kde(x_grid)
        s = rr.stats_spread
        ax_kde.plot(x_grid, y, color=color, linewidth=2,
                    label=f"{rr.route.label}  (P50=${s.median:+.2f})")
        ax_kde.fill_between(x_grid, y, alpha=0.10, color=color)

    kde_opt = stats.gaussian_kde(opt.optimal_spread)
    y_opt = kde_opt(x_grid)
    s_opt = opt.stats_optimal_spread
    ax_kde.plot(x_grid, y_opt, color=COLORS["mc_optimal"], linewidth=2.5,
                linestyle="--",
                label=f"Optimal  (P50=${s_opt.median:+.2f})")

    y_peak = y_opt.max()
    for pval, pname in [(s_opt.p05, "P5"), (s_opt.median, "P50"), (s_opt.p95, "P95")]:
        ax_kde.axvline(pval, color=COLORS["mc_optimal"], linewidth=1,
                       linestyle=":", alpha=0.7)
        ax_kde.text(pval, y_peak * 1.03, pname, ha="center", fontsize=8,
                    color=COLORS["mc_optimal"], fontweight="bold")

    ax_kde.axvline(0, color="black", linewidth=1, linestyle="--", alpha=0.4)
    if x_lo < 0:
        ax_kde.axvspan(x_lo, 0, alpha=0.04, color=COLORS["arb_closed"])
    ax_kde.axvspan(max(0, x_lo), x_hi, alpha=0.04, color=COLORS["arb_open"])

    ax_kde.set_xlabel("Arbitrage Spread ($/MMBtu)")
    ax_kde.set_ylabel("Probability Density")
    ax_kde.set_title("Spread Probability Density — All Routes")
    ax_kde.legend(loc="upper left", fontsize=9, framealpha=0.9)

    # ── Right panel: Route selection bar chart ──
    ax_bar = fig.add_subplot(gs[0, 1])
    labels = opt.route_labels
    probs = [opt.route_selection_prob[lb] for lb in labels]
    bar_colors = (_ROUTE_COLORS + [COLORS["mc_nogo"]])[: len(labels)]

    bars = ax_bar.barh(labels, probs, color=bar_colors, edgecolor="white",
                       linewidth=1.2, height=0.6)
    for bar, p in zip(bars, probs):
        if p > 0.005:
            ax_bar.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                        f"{p:.1%}", va="center", fontsize=10, fontweight="bold")
    ax_bar.set_xlim(0, max(probs) * 1.25 if max(probs) > 0 else 1)
    ax_bar.set_xlabel("Selection Probability")
    ax_bar.set_title("Route Choice", fontsize=12)
    ax_bar.invert_yaxis()

    # ── Bottom panel: stats summary table ──
    ax_tbl = fig.add_subplot(gs[1, :])
    ax_tbl.axis("off")

    col_labels = ["Route", "Mean", "P5", "P50", "P95",
                  "VaR 5%", "CVaR 5%", "P(>0)", "P(>$1)"]
    table_data = []
    for rr in route_results:
        s = rr.stats_spread
        table_data.append([
            rr.route.label,
            f"${s.mean:+.2f}", f"${s.p05:+.2f}", f"${s.median:+.2f}",
            f"${s.p95:+.2f}", f"${s.var_5pct:+.2f}", f"${s.cvar_5pct:+.2f}",
            f"{s.prob_positive:.1%}", f"{s.prob_above_1:.1%}",
        ])
    table_data.append([
        "Optimal",
        f"${s_opt.mean:+.2f}", f"${s_opt.p05:+.2f}", f"${s_opt.median:+.2f}",
        f"${s_opt.p95:+.2f}", f"${s_opt.var_5pct:+.2f}", f"${s_opt.cvar_5pct:+.2f}",
        f"{s_opt.prob_positive:.1%}", f"{s_opt.prob_above_1:.1%}",
    ])

    tbl = ax_tbl.table(cellText=table_data, colLabels=col_labels,
                       loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1.0, 1.6)

    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#37474F")
        tbl[0, j].set_text_props(color="white", fontweight="bold")
    last_row = len(table_data)
    for j in range(len(col_labels)):
        tbl[last_row, j].set_facecolor("#FFF3E0")

    ax_tbl.text(
        0.5, -0.05,
        f"Option Premium (Destination Flexibility): "
        f"${opt.option_premium_spread:+.4f}/MMBtu   |   "
        f"${opt.option_premium_tce:+,.0f}/day",
        ha="center", fontsize=10, fontstyle="italic",
        transform=ax_tbl.transAxes,
    )

    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    return fig


def plot_mc_tce_comparison(
    mc_output: MCSpreadOutput,
    save_path: str = None,
) -> plt.Figure:
    """
    Chart 06: TCE (Time Charter Equivalent) distribution comparison.
    Reveals the time-cost truth: shorter routes may win on daily profit
    even when their per-unit spread is lower.
    """
    route_results = mc_output.route_results
    n_routes = len(route_results)

    fig, axes = plt.subplots(1, 2, figsize=(15, 7),
                             gridspec_kw={"width_ratios": [2, 1]})
    fig.suptitle(
        "TCE Distribution — Profit per Day of Capital Committed",
        fontsize=15, fontweight="bold", y=0.98,
    )

    # ── Left: overlapping KDE ──
    ax1 = axes[0]
    x_grid_min, x_grid_max = np.inf, -np.inf
    for rr in route_results:
        x_grid_min = min(x_grid_min, rr.tce.min())
        x_grid_max = max(x_grid_max, rr.tce.max())
    margin = (x_grid_max - x_grid_min) * 0.08
    x_grid = np.linspace(x_grid_min - margin, x_grid_max + margin, 500)

    for rr, color in zip(route_results, _ROUTE_COLORS):
        kde = stats.gaussian_kde(rr.tce)
        y = kde(x_grid)
        ax1.plot(x_grid, y, color=color, linewidth=2,
                 label=f"{rr.route.label}")
        ax1.fill_between(x_grid, y, alpha=0.12, color=color)
        ax1.axvline(rr.stats_tce.mean, color=color, linewidth=1.2,
                    linestyle="--", alpha=0.6)

    ax1.set_xlabel("TCE ($/day)")
    ax1.set_ylabel("Probability Density")
    ax1.set_title("TCE Density — All Routes")
    ax1.legend(loc="upper left", fontsize=10)
    ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    # ── Right: horizontal bar of mean TCE + spread ──
    ax2 = axes[1]
    labels = [rr.route.label for rr in route_results]
    mean_tce = [rr.stats_tce.mean for rr in route_results]
    mean_spread = [rr.stats_spread.mean for rr in route_results]

    y_pos = np.arange(n_routes)

    bars = ax2.barh(y_pos, mean_tce, color=_ROUTE_COLORS[:n_routes],
                    edgecolor="white", linewidth=1.2, height=0.5)
    for bar, tce_val, sp_val in zip(bars, mean_tce, mean_spread):
        ax2.text(bar.get_width() + max(mean_tce) * 0.02,
                 bar.get_y() + bar.get_height() / 2,
                 f"${tce_val:,.0f}/d\n(spread ${sp_val:+.2f})",
                 va="center", fontsize=9, fontweight="bold")

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(labels, fontsize=10)
    ax2.set_xlabel("Mean TCE ($/day)")
    ax2.set_title("Mean TCE vs Spread", fontsize=12)
    ax2.invert_yaxis()
    ax2.set_xlim(0, max(mean_tce) * 1.40)
    ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))

    best_tce_idx = int(np.argmax(mean_tce))
    best_spread_idx = int(np.argmax(mean_spread))
    if best_tce_idx != best_spread_idx:
        note = (f"Insight: {labels[best_tce_idx]} has the highest TCE "
                f"despite {labels[best_spread_idx]} having the highest spread. "
                f"Shorter voyage = faster capital turnover.")
    else:
        note = f"{labels[best_tce_idx]} leads on both spread and TCE."

    fig.text(0.5, 0.01, note, ha="center", fontsize=10, fontstyle="italic",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFF3E0", alpha=0.9))

    plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    return fig


def plot_mc_sensitivity_tornado(
    mc_output: MCSpreadOutput,
    save_path: str = None,
    top_n: int = 8,
) -> plt.Figure:
    """
    Chart 07: Tornado sensitivity chart — which input factors drive
    the most variance in the optimal spread.
    """
    sens_list = mc_output.sensitivity.get("Optimal", [])
    if not sens_list:
        sens_list = list(mc_output.sensitivity.values())[0]

    sens_list = sens_list[:top_n]

    fig, axes = plt.subplots(1, 2, figsize=(15, 7),
                             gridspec_kw={"width_ratios": [1, 1]})
    fig.suptitle(
        "Sensitivity Analysis — What Drives Spread Variance?",
        fontsize=15, fontweight="bold", y=0.98,
    )

    # ── Left: variance contribution bars ──
    ax1 = axes[0]
    factors = [s.factor for s in reversed(sens_list)]
    contributions = [s.variance_contribution_pct for s in reversed(sens_list)]
    rho_values = [s.spearman_corr for s in reversed(sens_list)]
    bar_colors = [
        COLORS["mc_positive"] if rho >= 0 else COLORS["mc_negative"]
        for rho in rho_values
    ]

    y_pos = np.arange(len(factors))
    bars = ax1.barh(y_pos, contributions, color=bar_colors, edgecolor="white",
                    linewidth=1, height=0.6, alpha=0.85)

    for bar, pct in zip(bars, contributions):
        if pct > 1.0:
            ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                     f"{pct:.1f}%", va="center", fontsize=10, fontweight="bold")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(factors, fontsize=11)
    ax1.set_xlabel("Variance Contribution (%)")
    ax1.set_title("Factor Importance (Optimal Spread)")
    ax1.set_xlim(0, max(contributions) * 1.20 if contributions else 100)

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS["mc_positive"], label="Factor up → Spread up"),
        Patch(facecolor=COLORS["mc_negative"], label="Factor up → Spread down"),
    ]
    ax1.legend(handles=legend_elements, loc="lower right", fontsize=9)

    # ── Right: Spearman rho bars ──
    ax2 = axes[1]
    rho_colors = [
        COLORS["mc_positive"] if r >= 0 else COLORS["mc_negative"]
        for r in rho_values
    ]

    ax2.barh(y_pos, rho_values, color=rho_colors, edgecolor="white",
             linewidth=1, height=0.6, alpha=0.85)

    for i, rho in enumerate(rho_values):
        offset = 0.02 if rho >= 0 else -0.02
        ha = "left" if rho >= 0 else "right"
        ax2.text(rho + offset, y_pos[i],
                 f"{rho:+.3f}", va="center", ha=ha, fontsize=10, fontweight="bold")

    ax2.axvline(0, color="black", linewidth=0.8, linestyle="-")
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(factors, fontsize=11)
    ax2.set_xlabel("Spearman Rank Correlation (ρ)")
    ax2.set_title("Direction & Strength of Effect")
    rho_abs_max = max(abs(r) for r in rho_values) if rho_values else 1
    ax2.set_xlim(-rho_abs_max * 1.3, rho_abs_max * 1.3)

    jera = mc_output.jera_margin
    fig.text(
        0.5, 0.01,
        f"JERA Divert Probability: {jera.divert_probability:.1%}  |  "
        f"Domestic Revenue Threshold: {jera.domestic_revenue_jpy:,.0f} JPY/MMBtu",
        ha="center", fontsize=10, fontstyle="italic",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#E3F2FD", alpha=0.9),
    )

    plt.tight_layout(rect=[0, 0.05, 1, 0.95])

    if save_path:
        fig.savefig(save_path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        print(f"[Visualizer] ✓ Chart saved: {save_path}")
    return fig
