# 🌊 Global LNG Arbitrage Monitor

A comprehensive Python-based energy analysis tool for monitoring global LNG arbitrage opportunities (US-Asia vs US-Europe) and analyzing macro sentiment impact on exchange rates using NLP.

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Key Modules](#key-modules)
- [Output](#output)
- [Technical Details](#technical-details)
- [License](#license)

## ✨ Features

- **Real-time Market Data**: Fetches Henry Hub, TTF, and USD/JPY data from Yahoo Finance
- **Synthetic JKM Data**: Generates realistic JKM (Japan Korea Marker) prices based on TTF + Asian premium
- **LNG Economics Calculator**: 
  - Voyage time calculation
  - Boil-off loss (BOG) modeling using exponential decay
  - Complete shipping cost analysis
  - Netback calculation for arbitrage detection
- **NLP Sentiment Analysis**: 
  - Analyzes central bank meeting minutes (Fed/BOJ)
  - Hawkish/Dovish scoring using TextBlob + custom keyword dictionaries
  - Correlation analysis with USD/JPY volatility
- **Professional Visualizations**: 
  - Global gas price spreads
  - Arbitrage window comparison charts
  - Macro sentiment impact scatter plots
  - Historical netback time series

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/LNG_Arbitrage_Monitor.git
cd LNG_Arbitrage_Monitor
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Download NLTK Corpora (for TextBlob)

```bash
python -m textblob.download_corpora
```

## 📖 Usage

### Basic Usage

Simply run the main script:

```bash
python main.py
```

The program will:
1. Fetch market data (Henry Hub, TTF, JKM, USD/JPY)
2. Calculate LNG economics (netback, arbitrage windows)
3. Analyze central bank sentiment
4. Generate professional charts
5. Output trading signals

### Output

All outputs are saved to the `data/` directory:
- `market_data.csv` - Merged market data
- `01_global_gas_spreads.png` - Price comparison chart
- `02_arbitrage_netback.png` - Arbitrage window analysis
- `03_macro_sentiment.png` - Sentiment vs FX volatility
- `04_historical_netback.png` - Historical netback trends

### Example Output

```
╔══════════════════════════════════════════════════════════════╗
║                  📋 TRADING SIGNAL SUMMARY                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  [LNG Arbitrage]                                            ║
║  ├─ Europe Netback:    $  8.51/MMBtu  (Spread: $+5.09) ║
║  ├─ Asia (Panama):     $  9.62/MMBtu  (Spread: $+6.20) ║
║  └─ Asia (COGH):       $  8.88/MMBtu  (Spread: $+5.46) ║
║                                                              ║
║  🟢 RECOMMENDATION:                                       ║
║  STRONG BUY: Suggest Cargo Diversion to Asia (Panama)       ║
╚══════════════════════════════════════════════════════════════╝
```

## 📁 Project Structure

```
LNG_Arbitrage_Monitor/
│
├── data/                   # Output directory (charts and CSV files)
│   ├── market_data.csv
│   ├── 01_global_gas_spreads.png
│   ├── 02_arbitrage_netback.png
│   ├── 03_macro_sentiment.png
│   └── 04_historical_netback.png
│
├── src/
│   ├── __init__.py
│   ├── config.py           # Physical constants, shipping parameters, routes
│   ├── data_loader.py      # Market data fetching (Yahoo Finance)
│   ├── lng_economics.py    # Core LNG economics calculations
│   ├── macro_sentiment.py  # NLP sentiment analysis
│   └── visualizer.py       # Chart generation
│
├── main.py                 # Main program entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── .gitignore             # Git ignore rules
```

## 🔧 Key Modules

### `src/config.py`
Contains domain knowledge constants:
- Physical conversions (MMBtu to MWh, ton to MMBtu)
- Shipping parameters (vessel speeds, boil-off rates, canal fees)
- Route distances (US Gulf → Europe/Asia)
- Market data tickers

### `src/data_loader.py`
- Fetches real-time data from Yahoo Finance
- Generates synthetic JKM data (since JKM is paid data)
- Handles data merging and preprocessing

### `src/lng_economics.py`
Core LNG economics engine:
- `LNGCalculator` class with methods for:
  - Voyage day calculation
  - Boil-off loss (exponential decay model)
  - Shipping cost breakdown
  - Netback calculation
  - Arbitrage window detection

### `src/macro_sentiment.py`
NLP analysis module:
- TextBlob-based sentiment analysis
- Custom hawkish/dovish keyword matching
- Fed/BOJ stance scoring
- Correlation with USD/JPY volatility

### `src/visualizer.py`
Professional chart generation:
- Matplotlib/Seaborn-based visualizations
- Energy industry color schemes
- Publication-ready figures

## 📊 Technical Details

### Boil-off Loss Model

Uses exponential decay:
```
Remaining Volume = V₀ × (1 - r)^d
Loss Volume = V₀ × [1 - (1 - r)^d]
```
Where:
- V₀ = Initial volume (MMBtu)
- r = Daily evaporation rate (default: 0.15%)
- d = Voyage days

### Netback Formula

```
Netback = Destination Price × (1 - BOG Ratio)
          - Shipping Cost/Unit
          - Canal Fee/Unit
          - Liquefaction Fee
```

Arbitrage window opens when: `Netback > Henry Hub Price`

### Sentiment Analysis

Combines:
1. **TextBlob Polarity**: General sentiment [-1, 1]
2. **Keyword Matching**: Hawkish/Dovish dictionaries
3. **Net Score**: `Hawkish Score - Dovish Score` [-1, 1]

## 🔑 Key Parameters

Default values (configurable in `src/config.py`):
- **Charter Rate**: $60,000/day
- **Liquefaction Cost**: $3.0/MMBtu
- **Boil-off Rate**: 0.15%/day
- **Panama Canal Fee**: $400,000
- **Vessel Speed**: 17 knots (laden), 16 knots (ballast)

## 📝 Notes

- **JKM Data**: Since JKM is paid data from S&P Global Platts, the project generates synthetic JKM prices based on TTF + Asian premium + seasonal factors
- **Central Bank Minutes**: Uses sample text for demonstration. In production, you would fetch real meeting minutes from Fed/BOJ websites
- **Market Data**: Requires internet connection to fetch data from Yahoo Finance

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open source and available under the MIT License.

## 👤 Author

Created as a professional energy trading analytics tool.

## 🙏 Acknowledgments

- Yahoo Finance for market data API
- TextBlob/NLTK for NLP capabilities
- Matplotlib/Seaborn for visualization

---

**Disclaimer**: This tool is for educational and research purposes. Trading decisions should be made based on comprehensive analysis and professional advice.
