> **Related Project**: This project is designed to work alongside the [Structural Event Study Framework for LNG Energy Markets](https://github.com/EdisonLee9111/Structural-Event-Study-Framework-for-LNG-Energy-Markets). The event study framework identifies and quantifies structural shocks to LNG markets, while this monitor provides the probabilistic spread and hedge distribution engine — together they form a complete **event-driven → spread-response** analytical pipeline.

# Global LNG Arbitrage Monitor

A quantitative analytics pipeline for monitoring US Gulf Coast LNG export arbitrage opportunities to Europe and Asia. The system runs from raw market data ingestion through stochastic parameter modeling, correlation structure estimation, **10,000-scenario Monte Carlo simulation**, and **financial swap / FFA hedge overlay** — producing full spread / TCE probability distributions, Real Option valuation, hedge effectiveness analysis, and probabilistic trading signals.

---

## Pipeline Overview

| Step | Module | Output |
|------|--------|--------|
| 1 | `data_loader` | 1-year daily prices: HH, TTF, JKM (synthetic), USD/JPY |
| 1b | `parameter_inventory` | Parameter classification table (Must / Should / Optional / Defer) |
| 2 | `distribution_selection` | Distribution family assignments + analytically fitted parameters |
| 3 | `parameter_estimation` | Machine-readable `ParameterDistribution` objects with horizon projections; trader override support |
| 4 | `correlation_structure` | Historical correlation matrix → Gaussian Copula Cholesky factor |
| 5 | `validation_calibration` | Range checks, rolling-backtest coverage, extreme scenario audit |
| **6-MC** | **`monte_carlo_spread`** | **Vectorized Netback over 10,000 scenarios → Spread / TCE distributions, JERA margin, Real Option, sensitivity** |
| **6-SW** | **`swap_overlay`** | **Financial swap / FFA hedge overlay → hedged distribution, VaR reduction, ratio sensitivity, per-leg P&L attribution** |
| 6 | `lng_economics` | Single-point Netback & arb spread for 3 routes (reference baseline) |
| 7 | `macro_sentiment` | Fed / BOJ hawkish-dovish scoring; sentiment × USD/JPY correlation |
| 8 | `visualizer` | 8 publication-quality PNG charts (4 classic + 3 MC + 1 swap hedge) |
| **8b** | **`main`** | **Probabilistic trading signal: P(profit), VaR / CVaR, option premium, JERA divert alert** |

---

## Project Structure

```
LNG_Arbitrage_Monitor/
├── main.py                              # Pipeline entry point (Steps 1–8b)
├── requirements.txt
├── src/
│   ├── config.py                        # Physical constants, routes, tickers, NLP dictionaries, swap defaults
│   ├── data_loader.py                   # Yahoo Finance ingestion + JKM synthesis + OU fallbacks
│   ├── lng_economics.py                 # LNGCalculator: voyage, BOG, shipping cost, Netback
│   ├── monte_carlo_spread.py            # Layer 2: vectorized MC Netback, TCE, JERA, Real Option
│   ├── swap_overlay.py                  # Layer 3: financial swap / FFA hedge overlay on MC distribution
│   ├── macro_sentiment.py               # MacroSentimentAnalyzer: TextBlob + keyword + FX correlation
│   ├── parameter_inventory.py           # Step 1b: classify inputs by volatility & priority
│   ├── distribution_selection.py        # Step 2: fit distribution families
│   ├── parameter_estimation.py          # Step 3: machine-readable fitted parameters + projections
│   ├── correlation_structure.py         # Step 4: log-return correlation → Gaussian Copula
│   ├── validation_calibration.py        # Step 5: range / coverage / extreme audit
│   └── visualizer.py                    # 8 Matplotlib charts (classic + MC + swap hedge)
└── data/                                # All outputs land here
    ├── market_data.csv
    ├── step1_parameter_inventory_auto.csv / .md
    ├── step2_distribution_selection.csv / .md
    ├── step3_parameter_estimates.csv / .json / .md
    ├── step4_correlation_matrix.csv / step4_correlation_structure.json / .md
    ├── step5_validation_scenarios.csv / step5_validation_report.md
    ├── mc_spread_scenarios.csv          # 10,000 enriched scenarios with spreads / TCE / JERA
    ├── mc_spread_report.md              # Full distribution statistics report
    ├── swap_overlay_report.md           # Hedge effectiveness report
    ├── 01_global_gas_spreads.png
    ├── 02_arbitrage_netback.png
    ├── 03_macro_sentiment.png
    ├── 04_historical_netback.png
    ├── 05_mc_spread_distribution.png    # KDE overlay + route selection + stats table
    ├── 06_mc_tce_comparison.png         # TCE density + mean TCE vs spread bar
    ├── 07_mc_sensitivity_tornado.png    # Factor importance + Spearman rho direction
    └── 08_swap_hedge_overlay.png        # Hedged vs unhedged KDE + ratio sensitivity + per-leg P&L
```

---

## Installation

```bash
git clone https://github.com/EdisonLee9111/-Global-LNG-Arbitrage-Monitor.git
cd LNG_Arbitrage_Monitor
pip install -r requirements.txt
python -m textblob.download_corpora
```

**Requirements:** Python 3.10+, internet connection for Yahoo Finance.

## Usage

```bash
python main.py
```

---

## Module Details

### `src/data_loader.py`

Fetches via `yfinance`:
- **Henry Hub** (`NG=F`) — NYMEX natural gas futures, $/MMBtu
- **TTF** (`TTF=F`) — ICE TTF in €/MWh, auto-converted to $/MMBtu using live EUR/USD
- **USD/JPY** (`JPY=X`)

**JKM synthesis** (S&P Global Platts JKM is paid data):

```
JKM = TTF_$/MMBtu + $1.5 Asian premium + seasonal_factor + noise
```

Winter (Nov–Mar) adds +$0.8/MMBtu heating demand premium. All fetchers include OU mean-reversion synthetic fallbacks if Yahoo Finance returns empty data.

---

### `src/lng_economics.py` — `LNGCalculator`

**Voyage calculation:**

```
Laden days   = distance_nm / (17 knots × 24)
Ballast days = distance_nm / (16 knots × 24)
Round trip   = laden + ballast + loading (1.5d) + unloading (2.0d)
```

**Boil-off loss (exponential decay):**

```
Remaining = V₀ × (1 − r)^d
Loss      = V₀ × [1 − (1 − r)^d]
```

Default r = 0.15%/day. BOG is treated as opportunity cost even on MEGI/X-DF vessels.

**Netback formula:**

```
Netback = Dest_Price × (1 − BOG_ratio) − Shipping_$/MMBtu − Canal_$/MMBtu − Liquefaction_$/MMBtu
```

**Routes:**

| Route | Distance | Canal |
|-------|----------|-------|
| US Gulf → Rotterdam | 5,000 nm | None |
| US Gulf → Tokyo (Panama) | 9,200 nm | Panama ($400k) |
| US Gulf → Tokyo (COGH) | 14,500 nm | None |

---

### `src/monte_carlo_spread.py` — Layer 2: MC Spread Engine

Bridges Step 5 correlated scenarios (10,000 draws) into the Netback economics engine, transforming single-point values into full probability distributions.

**Architecture:**

| Phase | Function | Description |
|-------|----------|-------------|
| A (scalar) | `resolve_route_constants()` | Pre-resolve deterministic voyage parameters from `config.ROUTES` |
| B (vectorized) | `vectorized_netback()` | NumPy-broadcast Netback / Spread / TCE over all scenarios (< 1 ms for 10,000 rows) |
| JERA | `compute_jera_domestic_margin()` | `Import_Cost_JPY = JKM × USD_JPY` vs domestic revenue threshold |
| C (cross-route) | `compute_optimal_strategy()` | Real Option: `max(Spread_EU, Spread_Asia_Panama, Spread_Asia_COGH, 0)` + option premium |
| Stats | `compute_distribution_stats()` | P5/P25/P50/P75/P95, VaR, CVaR, success probability, skewness, kurtosis |
| Sensitivity | `sensitivity_analysis()` | Spearman rank correlation → normalized variance contribution per factor |

**Vectorized Netback** replicates `LNGCalculator.calculate_netback()` exactly (verified to `1e-8` tolerance), using NumPy broadcasting:

```
laden_days      = base_laden_days + Voyage_Delay           # stochastic delay
remaining_ratio = (1 − BOG_Rate)^laden_days                # exponential decay
delivered       = cargo × remaining_ratio
shipping/unit   = RT_days × (Charter + Fuel) / delivered   # round-trip allocation
netback         = dest_price × (1 − bog_ratio) − shipping/unit − canal/unit − liquefaction
spread          = netback − HH_Price
TCE             = (spread × cargo_size) / RT_days           # $/day profit
```

**TCE (Time Charter Equivalent)** normalizes profit by voyage duration, revealing time-cost effects invisible in raw spread:

| Route | Spread (P50) | TCE (mean) | Insight |
|-------|-------------|-----------|---------|
| Europe (Rotterdam) | $3.09 | $333k/day | Highest daily profit — short round-trip |
| Asia (Tokyo-Panama) | $4.11 | $275k/day | Higher spread but longer capital commitment |
| Asia (Tokyo-COGH) | $3.44 | $156k/day | Worst TCE despite second-best spread |

**JERA Domestic Margin:**

```
Import_Cost_JPY     = JKM_Price × USD_JPY
Domestic_Profit_JPY = 1,500 JPY/MMBtu − Import_Cost_JPY
```

When `Domestic_Profit < 0`, JERA should divert the cargo to the spot market. The divert probability is a key signal for Asian LNG demand.

**Real Option — Destination Flexibility:**

```
Optimal_Spread[i] = max(Spread_EU[i], Spread_Asia_Panama[i], Spread_Asia_COGH[i], 0)
Option_Premium    = E[Optimal_Spread] − max(E[Spread_EU], E[Spread_Asia])
```

The no-go floor (`0`) represents the option not to ship. The option premium quantifies the pure value of destination flexibility.

**Sensitivity Analysis** ranks each input factor's variance contribution via squared Spearman rank correlation:

| Factor | Typical Contribution |
|--------|---------------------|
| JKM / TTF Price | 50–65% |
| HH Price | 15–25% |
| Charter Rate | 3–8% |
| Fuel Cost | 3–6% |
| Voyage Delay | 1–3% |
| BOG Rate | < 1% |

Outputs: `mc_spread_scenarios.csv` (10,000 enriched rows) / `mc_spread_report.md`

---

### `src/swap_overlay.py` — Layer 3: Financial Swap / FFA Hedge Overlay

Applies financial swap P&L on top of the physical spread distributions produced by the MC engine. **Zero-invasive**: reads `MCSpreadOutput` as input, produces `HedgedOutput` as output without touching any upstream calculation logic.

**Hedging scope — 4 legs, independently configurable:**

| Leg | Instrument | Settlement | Direction | Default |
|-----|-----------|-----------|-----------|---------|
| HH | NYMEX Henry Hub swap | $/MMBtu, vs spot | Pay Fixed / Receive Float | **On, h = 80%** |
| JKM | Platts JKM swap | $/MMBtu, vs spot | Receive Fixed / Pay Float | **On, h = 80%** |
| Charter | FFA (Freight Forward Agreement) | $/day, vs Baltic rate | Pay Fixed / Receive Float | Off, h = 50% |
| FX | USD/JPY forward | %, vs spot | — | Off, h = 50% |

**Why FFA settles at TCE level, not spread level:**

Charter rate ($/day) cannot be directly added to spread ($/MMBtu). The FFA P&L is converted to $/MMBtu via the scenario-specific round-trip days of the optimal chosen route:

```
ffa_pnl_mmbtu[i] = h_charter × (Charter_spot[i] − FFA_rate) × rt_days[i] / cargo_size
```

This uses `cargo_size` (not delivered volume) as the denominator — a 1–3% approximation whose residual is absorbed into the structural basis risk.

**4-step calculation pipeline:**

| Step | Function | Description |
|------|----------|-------------|
| 1 | `resolve_swap_rates()` | `auto` mode: rate = MC mean (fair value); `manual` mode: trader's broker quote |
| 2 | `compute_swap_pnl()` | Vectorized P&L across all 10,000 scenarios — 3 NumPy operations |
| 3 | `overlay_on_spread()` | `hedged_spread = optimal_spread + total_pnl`; `hedged_tce` derived consistently |
| 4 | `compute_hedge_effectiveness()` | Variance reduction, VaR/CVaR improvement, Sharpe, P(loss) change, basis risk note |

**Effectiveness metrics:**

| Metric | Formula |
|--------|---------|
| Variance Reduction | `1 − Var(hedged) / Var(unhedged)` |
| VaR Reduction | `VaR_unhedged − VaR_hedged` ($/MMBtu) |
| CVaR Reduction | `CVaR_unhedged − CVaR_hedged` |
| Hedge Cost | `E[unhedged] − E[hedged]` (positive = premium paid) |
| Sharpe Improvement | `Sharpe_hedged − Sharpe_unhedged` |
| P(loss) Change | `P(hedged < 0) − P(unhedged < 0)` |

**Hedge Ratio Sensitivity Table** sweeps h ∈ {0%, 25%, 50%, 75%, 100%} uniformly across all enabled legs, showing the VaR / CVaR / variance reduction trade-off at each ratio. Helps traders identify the optimal hedge ratio.

**Structural basis risk (important limitation):**

Even at 100% JKM hedge ratio, the swap only covers the JKM coefficient embedded in Netback:

```
Netback = JKM × (1 − BOG_ratio) − shipping − canal − liquefaction
```

So a 100% JKM swap hedges approximately `(1 − BOG_ratio) ≈ 95–98%` of the Netback's JKM exposure. The remaining 2–5% is irreducible structural basis risk from BOG decay, voyage-time variability, and the non-linear cost structure. This residual is computed and flagged explicitly in both the console output and the report.

**Configuration (in `config.DEFAULT_SWAP_SPEC`):**

```python
DEFAULT_SWAP_SPEC = {
    "mode": "auto",                      # "auto" = MC mean as swap rate
    "hh":      {"enabled": True,  "hedge_ratio": 0.8, "swap_rate": None},
    "jkm":     {"enabled": True,  "hedge_ratio": 0.8, "swap_rate": None},
    "charter": {"enabled": False, "hedge_ratio": 0.5, "swap_rate": None},
    "fx":      {"enabled": False, "hedge_ratio": 0.5, "swap_rate": None},
    "notional_mmbtu":  3_744_000,
    "basis_noise_std": 0.0,
}
```

To use manual rates from broker quotes, set `"mode": "manual"` and supply `"swap_rate"` for each enabled leg. The difference from the MC mean becomes the implied hedge cost / premium.

Outputs: `swap_overlay_report.md`

---

### `src/parameter_inventory.py` — Step 1b

Builds a runtime inventory of all Netback inputs from live data and `config.py`:

| Priority | Parameters |
|----------|-----------|
| **Must model** | HH price, TTF price, JKM price, Charter rate, USD/JPY |
| **Should model** | Fuel cost, Voyage days |
| **Optional** | BOG boil-off rate |
| **Defer** | Canal fee, Liquefaction fee |

Outputs: `step1_parameter_inventory_auto.csv / .md`

---

### `src/distribution_selection.py` — Step 2

Selects distribution families for each uncertain input over a 30–60 day cargo horizon:

| Parameter | Distribution | Notes |
|-----------|-------------|-------|
| HH / TTF / JKM prices | OU mean-reversion (primary) + GBM (fallback) | OU via OLS discrete regression |
| Charter rate | Lognormal + optional jump | Regime-aware σ: 0.35 / 0.45 / 0.60 |
| Fuel cost | Lognormal | Correlated with HH/JKM for MEGI/X-DF vessels |
| Voyage delay | Shifted Gamma (k=2, θ=1.5) | Panama dry-season (Jan–Apr) +3 day shift |
| BOG rate | Scaled Beta on [0.08%, 0.15%] | Triangular simplification available |
| USD/JPY | Normal returns | Override with option IV when available |

Outputs: `step2_distribution_selection.csv / .md`

---

### `src/parameter_estimation.py` — Step 3

Produces machine-readable `ParameterDistribution` objects with fitted numerical parameters and horizon projections (default T = 45 trading days). Three estimation methods:

- **historical** — OLS-estimated OU/GBM from trailing 1-year window (gas prices, USD/JPY)
- **expert_prior** — regime-calibrated lognormal (charter rate, fuel cost)
- **manual** — triangular distribution from domain bounds (BOG rate)

**Horizon projections** expose P05 / P95 confidence intervals:

| Distribution | Projection formula |
|-------------|-------------------|
| OU | `E[X_T] = θ + (S₀−θ)e^{−κT}`, `Var = σ²/(2κ)(1−e^{−2κT})` |
| GBM / Lognormal | `log(S_T/S₀) ~ N((μ−σ²/2)T, σ²T)` |

Supports **trader overrides**: pass `overrides={"HH_Price": {"sigma": 0.50}}` to surgically replace any sub-parameter while preserving the original in `_base_params`.

Outputs: `step3_parameter_estimates.csv / .json / .md`

---

### `src/correlation_structure.py` — Step 4

Builds a Gaussian Copula for joint scenario generation:

1. **Historical correlation** — Pearson on daily log-returns for the 4 observable series (HH, TTF, JKM, USD/JPY)
2. **Charter rate proxy** — industry-knowledge prior (JKM~0.55, TTF~0.40, HH~0.20, FX~0.05); overridable
3. **Fuel cost proxy** — MEGI/X-DF correlated with energy prices (HH~0.75, JKM~0.70, TTF~0.60); overridable
4. **Nearest-PSD projection** — eigenvalue clipping ensures valid Cholesky decomposition after any override
5. **Cholesky factor L** — used in Step 5: `Z_corr = Z_indep @ L.T`, then `U = Φ(Z_corr)`

> **Note on JKM–TTF correlation:** since JKM is synthetic (TTF + premium + noise), the estimated ρ(JKM, TTF) ≈ 0.95+. With real Platts JKM data expect ρ ≈ 0.80–0.85. Use `pairwise_overrides={("JKM_Price","TTF_Price"): 0.82}` to correct this.

Outputs: `step4_correlation_matrix.csv / step4_correlation_structure.json / .md`

---

### `src/validation_calibration.py` — Step 5

Three-layer validation on 10,000 correlated Monte Carlo draws:

**A. Range check** — P1/P99 must stay within physical bounds (e.g. HH: $0.50–$50). Warns if >2% of draws fall outside.

**B. Historical coverage (rolling backtest)** — For each historical date *t*, project a 90% CI from `hist[t]` over horizon T, check if `hist[t+T]` falls inside. Target hit-rate: 80%–100%.

| Status | Meaning |
|--------|---------|
| PASS | Well-calibrated |
| TOO_NARROW | Volatility under-estimated; widen σ |
| TOO_WIDE | Volatility over-estimated; tighten σ |

**C. Extreme scenario audit** — surfaces 5 lowest + 5 highest draws per factor for trader review.

Outputs: `step5_validation_scenarios.csv / step5_validation_report.md`

---

### `src/macro_sentiment.py` — `MacroSentimentAnalyzer`

Multi-dimensional scoring of central bank minutes:

1. **TextBlob polarity** [-1, 1] and subjectivity [0, 1]
2. **Keyword matching** — regex word-boundary count against hawkish/dovish dictionaries
3. **Net score** = `hawkish_hits / total − dovish_hits / total` ∈ [-1, 1]
4. **Stance**: HAWKISH (>0.2), DOVISH (<−0.2), NEUTRAL

USD/JPY direction: `combined = Fed_net − BOJ_net`. `>0.3` → Bullish USD, `<−0.3` → Bearish USD.

Also computes 20-day rolling correlation between a dynamic sentiment index and realized USD/JPY volatility.

---

### `src/visualizer.py`

**Charts 01–04: Market Data & Single-Point Analysis**

| Chart | Content |
|-------|---------|
| `01_global_gas_spreads.png` | HH / TTF / JKM price series + spread bands |
| `02_arbitrage_netback.png` | Netback vs HH bar chart + arb spread status |
| `03_macro_sentiment.png` | Sentiment × FX volatility scatter + OLS line; hawk/dove bar chart |
| `04_historical_netback.png` | 1-year Netback time series + arb spread area chart |

**Charts 05–07: Monte Carlo Distribution Analysis**

| Chart | Content |
|-------|---------|
| `05_mc_spread_distribution.png` | KDE overlay of spread distributions for 3 routes + Optimal; P5/P50/P95 markers; route selection probability bar; summary statistics table with VaR/CVaR; option premium annotation |
| `06_mc_tce_comparison.png` | TCE ($/day) density curves with mean markers; mean TCE vs spread horizontal bar; auto-generated insight text highlighting time-cost divergence between routes |
| `07_mc_sensitivity_tornado.png` | Dual-panel tornado: left = variance contribution % (sorted), right = Spearman ρ direction & strength; JERA divert probability footer |

**Chart 08: Swap Hedge Overlay**

| Chart | Content |
|-------|---------|
| `08_swap_hedge_overlay.png` | 4-panel layout: (1) Hedged vs Unhedged KDE overlay with P5/P50/P95 markers and variance reduction annotation; (2) Hedge ratio sensitivity — VaR / CVaR / Variance Reduction vs h with current ratio marker; (3) Per-leg P&L attribution bar with P5–P95 error bars; (4) Effectiveness metrics comparison table with colour-coded delta column |

---

## Trading Signals

### Single-Point Signal (Step 8)

Classic threshold-based signal from the latest market snapshot:

| Condition | Signal |
|-----------|--------|
| Spread > $1.00 | STRONG BUY |
| $0 < Spread ≤ $1.00 | MARGINAL |
| Spread ≤ $0 | NO ARB |

### Probabilistic Signal (Step 8b — MC-Enhanced)

Upgraded signal using the full 10,000-scenario distribution:

| Condition | Signal |
|-----------|--------|
| P(profit) > 80% AND median spread > $1 | HIGH CONFIDENCE BUY |
| P(profit) > 60% | MODERATE — positive EV but tail risk |
| P(profit) > 40% | CAUTIOUS — near break-even |
| P(profit) ≤ 40% | AVOID — majority unprofitable |

Additional risk overlays:
- **VaR / CVaR**: 5th-percentile loss and expected shortfall
- **JERA Alert**: triggers when divert probability > 30% (JKM demand at risk)
- **FX Risk**: flags significant Fed/BOJ policy divergence affecting USD/JPY

---

## Key Parameters

| Parameter | Default | Config key |
|-----------|---------|------------|
| Charter rate | $60,000/day | `DEFAULT_CHARTER_RATE` |
| Fuel cost | $15,000/day | `DEFAULT_FUEL_COST_PER_DAY` |
| Liquefaction cost | $3.0/MMBtu | `DEFAULT_LIQUEFACTION_COST` |
| Boil-off rate | 0.15%/day | `BOIL_OFF_RATE` |
| Panama Canal fee | $400,000 | `CANAL_FEE_PANAMA` |
| Vessel speed (laden) | 17 knots | `LADEN_SPEED` |
| Cargo size | 160,000 m³ (~3.74M MMBtu) | `STANDARD_CARGO_SIZE_CBM` |
| JKM premium over TTF | $1.5/MMBtu | `JKM_PREMIUM_OVER_TTF` |
| JERA domestic revenue | 1,500 JPY/MMBtu | `JERA_DOMESTIC_REVENUE_JPY` |
| MC horizon | 45 trading days | `horizon_days=45` in Step 3 |
| MC sample size | 10,000 | `n_samples=10_000` in Step 5 |
| Swap mode | `auto` (MC mean) | `DEFAULT_SWAP_SPEC["mode"]` |
| HH hedge ratio | 80% | `DEFAULT_SWAP_SPEC["hh"]["hedge_ratio"]` |
| JKM hedge ratio | 80% | `DEFAULT_SWAP_SPEC["jkm"]["hedge_ratio"]` |
| Charter FFA | disabled | `DEFAULT_SWAP_SPEC["charter"]["enabled"]` |
| FX forward | disabled | `DEFAULT_SWAP_SPEC["fx"]["enabled"]` |

---

## Notes

- **JKM data**: S&P Global Platts JKM is paid data. The synthetic proxy (TTF + premium + seasonal noise) is adequate for spread direction analysis but should be replaced with a real feed in production — and the JKM–TTF correlation override applied in Step 4.
- **Central bank minutes**: the pipeline uses static sample text from `config.py`. In production, point `fetch_central_bank_text()` at a live scraper or EDGAR API feed.
- **Vectorized consistency**: `vectorized_netback()` in the MC engine has been verified against the scalar `LNGCalculator.calculate_netback()` to `1e-8` tolerance across all three routes.
- **TCE insight**: raw spread can be misleading — a route with higher spread but longer voyage may have worse daily profitability. The TCE metric normalizes for this, making cross-route comparison economically meaningful.
- **Swap basis risk**: even at 100% hedge ratio, the JKM swap only covers `JKM × (1 − BOG_ratio)` ≈ 95–98% of Netback's JKM exposure. The residual 2–5% from BOG decay, shipping cost allocation, and canal fee dilution is irreducible structural basis risk — reported explicitly in both console output and `swap_overlay_report.md`.

---

## Roadmap

### Asian Swap Module *(under consideration)*

The current swap overlay implements **European-style (bullet) settlement**: the swap P&L is calculated against the spot price at a single future date. In practice, many JKM-linked LNG contracts and shipping deals are priced against the **monthly average** of the spot price — this is the Asian swap (also called average rate swap or arithmetic Asian option).

The distinction matters for three reasons:

**1. Settlement mechanics differ:**

| Style | Settlement formula |
|-------|--------------------|
| European (current) | `h × (JKM_spot_at_T − fixed_rate)` |
| Asian (proposed) | `h × (avg(JKM_t₁, …, JKM_tₙ) − fixed_rate)` |

**2. The MC engine generates terminal snapshots, not paths:**

The current Step 5 / Step 6-MC pipeline samples each factor once at horizon T (a 45-day forward snapshot). Asian swap pricing requires knowing the full price path — the daily realizations *between* now and T — to compute the averaging period correctly. This means the path simulation layer would need to be added upstream of the existing engine, likely in `validation_calibration.py` or as a new `path_simulator.py` module.

**3. Variance compression reduces the swap rate:**

For a GBM process, the variance of the arithmetic average is lower than the terminal variance:
```
Var(avg) ≈ σ² × T/3    (for equally-spaced averaging over [0, T])
Var(spot_T) = σ² × T
```
This means the fair value of an Asian swap is lower than a European swap for the same notional and tenor — the Asian fixed rate should be cheaper. Ignoring this and using the current European MC mean as the Asian rate would **overstate the hedge cost** when buying protection.

**Proposed design sketch:**

- Add a `PathSpec` to `SwapSpec`: `settlement: "european" | "asian"`, `averaging_days: int`
- In `compute_swap_pnl()`, if `settlement == "asian"`: simulate N × averaging_days price paths via the OU/GBM parameters from Step 3, then average each path to get the realized index, then compute `h × (avg_realized − fixed_rate)`
- Reuse the existing Cholesky correlation structure to keep cross-factor dependencies intact
- The analytical Turnbull-Wakeman approximation for Asian options can provide a fast closed-form cross-check on the simulated fair value

This is the primary extension being evaluated before implementation begins.

---

## License

MIT
