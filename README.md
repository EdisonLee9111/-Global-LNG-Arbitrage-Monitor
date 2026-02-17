# Global LNG Arbitrage Monitor

End-to-end Python pipeline for monitoring US Gulf Coast LNG export arbitrage opportunities to Europe and Asia, with integrated NLP macro-sentiment analysis and Monte Carlo-ready parameter modeling.

## Overview

This project implements a quantitative LNG trading analytics workflow:

1. **Market Data Ingestion** - Pull Henry Hub, TTF, USD/JPY from Yahoo Finance; synthesize JKM (Platts paid data) via TTF + Asian premium + seasonal factors.
2. **Netback Calculation** - Compute delivered economics for three routes (US Gulf → Rotterdam, → Tokyo via Panama, → Tokyo via COGH), including voyage time, boil-off loss (exponential decay), shipping costs, and canal fees.
3. **Parameter Inventory (Step 1)** - Systematically classify all Netback input parameters by volatility profile and modeling priority (Must / Should / Optional / Defer).
4. **Distribution Selection (Step 2)** - Select distribution families (OU mean-reversion, GBM, Lognormal, Gamma, Beta) for uncertain inputs and estimate parameters from historical data, preparing for Monte Carlo simulation.
5. **NLP Sentiment Analysis** - Score Fed/BOJ meeting minutes for hawkish/dovish stance using TextBlob + custom keyword dictionaries; correlate with USD/JPY volatility.
6. **Visualization & Signals** - Generate publication-quality charts and output an integrated trading signal combining arbitrage spreads with macro sentiment.

## Project Structure

```
LNG_Arbitrage_Monitor/
├── main.py                          # Pipeline entry point (Steps 1-6)
├── requirements.txt                 # Python dependencies
├── src/
│   ├── config.py                    # Physical constants, route distances, market tickers
│   ├── data_loader.py               # Yahoo Finance data fetching & JKM synthesis
│   ├── lng_economics.py             # LNGCalculator: voyage, BOG, shipping, Netback
│   ├── macro_sentiment.py           # NLP sentiment analysis (TextBlob + keyword scoring)
│   ├── parameter_inventory.py       # Step 1: parameter classification & priority
│   ├── distribution_selection.py    # Step 2: distribution family selection & fitting
│   └── visualizer.py                # Matplotlib/Seaborn chart generation
└── data/                            # Output directory
    ├── market_data.csv
    ├── step1_parameter_inventory_auto.csv / .md
    ├── step2_distribution_selection.csv / .md
    ├── 01_global_gas_spreads.png
    ├── 02_arbitrage_netback.png
    ├── 03_macro_sentiment.png
    └── 04_historical_netback.png
```

## Installation

```bash
git clone https://github.com/EdisonLee9111/-Global-LNG-Arbitrage-Monitor.git
cd LNG_Arbitrage_Monitor
pip install -r requirements.txt
python -m textblob.download_corpora
```

**Requirements**: Python 3.10+, internet connection (Yahoo Finance API).

## Usage

```bash
python main.py
```

The pipeline runs six sequential steps and outputs:
- CSV/Markdown parameter inventory and distribution selection reports
- Four PNG charts (gas spreads, arbitrage netback, macro sentiment, historical netback)
- Console trading signal with route-level recommendations

## Key Parameters

| Parameter | Default | Source |
|---|---|---|
| Charter Rate | $60,000/day | `config.DEFAULT_CHARTER_RATE` |
| Liquefaction Cost | $3.0/MMBtu | `config.DEFAULT_LIQUEFACTION_COST` |
| Boil-off Rate | 0.15%/day | `config.BOIL_OFF_RATE` |
| Panama Canal Fee | $400,000 | `config.CANAL_FEE_PANAMA` |
| Vessel Speed (Laden) | 17 knots | `config.LADEN_SPEED` |
| Cargo Size | 160,000 m³ | `config.STANDARD_CARGO_SIZE_CBM` |

## Technical Notes

**Netback formula**:
```
Netback = Dest_Price × (1 - BOG_Ratio) - Shipping_Cost/Unit - Canal_Fee/Unit - Liquefaction_Fee
Arbitrage Signal: Netback > Henry_Hub_Price
```

**Boil-off model** (exponential decay):
```
Remaining = V₀ × (1 - r)^d,  where r = daily evaporation rate, d = voyage days
```

**Distribution modeling** (Step 2):
- Gas prices → Ornstein-Uhlenbeck mean-reversion (primary), GBM (fallback)
- Charter rate → Lognormal with regime-dependent volatility and optional jump process
- Voyage delay → Shifted Gamma (right-skew for weather/congestion)
- BOG rate → Scaled Beta on [0.08%, 0.15%]
- USD/JPY → Normal returns, scalable to option-implied vol when available

**JKM synthesis**: JKM = TTF + Asian premium ($1.5/MMBtu) + seasonal adjustment + noise, since S&P Global Platts JKM is paid data.

## License

MIT
