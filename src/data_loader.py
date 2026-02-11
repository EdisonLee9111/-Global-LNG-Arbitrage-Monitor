"""
data_loader.py - Market Data Loading Module
============================================
Responsible for fetching natural gas, LNG prices, and exchange rate data from Yahoo Finance.
Includes JKM synthetic data generation function (since JKM is paid data).
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import warnings
import os

from . import config

warnings.filterwarnings("ignore", category=FutureWarning)


def fetch_henry_hub(period: str = None, interval: str = None) -> pd.DataFrame:
    """
    Fetch NYMEX Henry Hub natural gas futures prices ($/MMBtu).
    
    Henry Hub is the benchmark pricing point for North American natural gas,
    located in Erath, Louisiana.
    NYMEX NG contracts are priced in $/MMBtu.
    
    Parameters
    ----------
    period : str
        Data time range, e.g., '1y', '6mo', etc.
    interval : str
        Data frequency, e.g., '1d', '1wk', etc.
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing Date and HH_Price columns
    """
    period = period or config.DATA_PERIOD
    interval = interval or config.DATA_INTERVAL
    
    print("[DataLoader] Fetching Henry Hub (NG=F) data...")
    try:
        ticker = yf.Ticker(config.TICKERS["henry_hub"])
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            print("[DataLoader] ⚠ Yahoo Finance returned empty data, using synthetic Henry Hub data")
            return _generate_synthetic_henry_hub()
        
        df = df[["Close"]].rename(columns={"Close": "HH_Price"})
        df.index.name = "Date"
        df.index = df.index.tz_localize(None)  # Remove timezone info
        print(f"[DataLoader] ✓ Retrieved {len(df)} Henry Hub data points")
        return df
        
    except Exception as e:
        print(f"[DataLoader] ⚠ Failed to fetch Henry Hub: {e}, using synthetic data")
        return _generate_synthetic_henry_hub()


def fetch_ttf(period: str = None, interval: str = None) -> pd.DataFrame:
    """
    Fetch ICE TTF natural gas futures prices (€/MWh) and convert to $/MMBtu.
    
    TTF (Title Transfer Facility) is the European natural gas pricing benchmark,
    published by the Dutch virtual trading point, priced in EUR/MWh.
    
    Conversion formula: $/MMBtu = (€/MWh) * (USD/EUR exchange rate) * MMBTU_TO_MWH
    
    Parameters / Returns: Same as fetch_henry_hub
    """
    period = period or config.DATA_PERIOD
    interval = interval or config.DATA_INTERVAL
    
    print("[DataLoader] Fetching TTF (TTF=F) data...")
    try:
        ticker = yf.Ticker(config.TICKERS["ttf"])
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            print("[DataLoader] ⚠ TTF=F returned empty data, using synthetic TTF data")
            return _generate_synthetic_ttf()
        
        df = df[["Close"]].rename(columns={"Close": "TTF_EUR_MWH"})
        df.index.name = "Date"
        df.index = df.index.tz_localize(None)
        
        # Fetch EUR/USD exchange rate for conversion
        eur_usd = _fetch_eur_usd(period, interval)
        df = df.join(eur_usd, how="left")
        df["EUR_USD"] = df["EUR_USD"].ffill().bfill()
        
        # Convert: €/MWh → $/MMBtu
        # $/MMBtu = (€/MWh) * ($/€) * (MWh/MMBtu)
        # i.e., $/MMBtu = (€/MWh) * EUR_USD * MMBTU_TO_MWH
        df["TTF_Price"] = df["TTF_EUR_MWH"] * df["EUR_USD"] * config.MMBTU_TO_MWH
        
        print(f"[DataLoader] ✓ Retrieved {len(df)} TTF data points")
        return df[["TTF_Price"]]
        
    except Exception as e:
        print(f"[DataLoader] ⚠ Failed to fetch TTF: {e}, using synthetic data")
        return _generate_synthetic_ttf()


def generate_synthetic_jkm(ttf_data: pd.DataFrame) -> pd.DataFrame:
    """
    Generate synthetic JKM (Japan Korea Marker) data.
    
    JKM is the Northeast Asian LNG spot benchmark price ($/MMBtu) published by S&P Global Platts.
    Since JKM is paid data, this function generates synthetic data based on TTF price 
    + Asian premium + random volatility.
    
    Synthetic logic:
    - Base price = TTF ($/MMBtu) + Asian premium ($1.5/MMBtu)
    - Add seasonal factors (winter demand season has higher premium)
    - Add random noise to simulate market volatility
    
    Parameters
    ----------
    ttf_data : pd.DataFrame
        TTF price data, must contain 'TTF_Price' column
        
    Returns
    -------
    pd.DataFrame
        DataFrame containing 'JKM_Price' column ($/MMBtu)
    """
    print("[DataLoader] Generating synthetic JKM data (TTF + Asian premium)...")
    
    np.random.seed(42)  # Fixed random seed for reproducibility
    
    df = ttf_data.copy()
    
    # Seasonal premium: Winter (Nov-Mar) Asian heating demand pushes up JKM
    months = df.index.month
    seasonal_premium = np.where(
        (months >= 11) | (months <= 3),
        0.8,   # Winter additional premium $0.8/MMBtu
        0.0    # Non-winter
    )
    
    # Random volatility (±$0.3/MMBtu)
    noise = np.random.normal(0, 0.3, len(df))
    
    # JKM = TTF + base Asian premium + seasonal + noise
    df["JKM_Price"] = (
        df["TTF_Price"] 
        + config.JKM_PREMIUM_OVER_TTF 
        + seasonal_premium 
        + noise
    )
    
    # Ensure prices are positive
    df["JKM_Price"] = df["JKM_Price"].clip(lower=1.0)
    
    print(f"[DataLoader] ✓ Generated {len(df)} synthetic JKM data points")
    return df[["JKM_Price"]]


def fetch_usd_jpy(period: str = None, interval: str = None) -> pd.DataFrame:
    """
    Fetch USD/JPY exchange rate data.
    
    USD/JPY exchange rate has significant impact on LNG trade:
    - Yen depreciation → Japanese buyers' actual costs rise → may suppress spot purchases
    - Yen appreciation → Japanese buyers' purchasing power increases → may boost JKM
    
    Returns
    -------
    pd.DataFrame
        DataFrame containing 'USD_JPY' column
    """
    period = period or config.DATA_PERIOD
    interval = interval or config.DATA_INTERVAL
    
    print("[DataLoader] Fetching USD/JPY exchange rate...")
    try:
        ticker = yf.Ticker(config.TICKERS["usd_jpy"])
        df = ticker.history(period=period, interval=interval)
        
        if df.empty:
            print("[DataLoader] ⚠ USD/JPY returned empty data, using synthetic data")
            return _generate_synthetic_usd_jpy()
        
        df = df[["Close"]].rename(columns={"Close": "USD_JPY"})
        df.index.name = "Date"
        df.index = df.index.tz_localize(None)
        print(f"[DataLoader] ✓ Retrieved {len(df)} USD/JPY data points")
        return df
        
    except Exception as e:
        print(f"[DataLoader] ⚠ Failed to fetch USD/JPY: {e}, using synthetic data")
        return _generate_synthetic_usd_jpy()


def fetch_central_bank_text(source: str = "sample") -> dict:
    """
    Fetch central bank meeting minutes text.
    
    Supports two modes:
    - 'sample': Use preset sample text in config.py (for demonstration)
    - URL: Fetch text from given URL list (requires network access)
    
    Parameters
    ----------
    source : str
        'sample' to use preset text, or pass URL
        
    Returns
    -------
    dict
        Text dictionary in format {'fed': str, 'boj': str}
    """
    if source == "sample":
        print("[DataLoader] Using preset central bank meeting minutes sample text...")
        return {
            "fed": config.SAMPLE_FED_MINUTES,
            "boj": config.SAMPLE_BOJ_MINUTES,
        }
    else:
        # Reserved network fetching interface
        print(f"[DataLoader] ⚠ URL fetching not implemented, falling back to sample text")
        return {
            "fed": config.SAMPLE_FED_MINUTES,
            "boj": config.SAMPLE_BOJ_MINUTES,
        }


def load_all_market_data() -> pd.DataFrame:
    """
    One-stop loading of all market data, merged into a unified DataFrame.
    
    Returns
    -------
    pd.DataFrame
        Merged data containing HH_Price, TTF_Price, JKM_Price, USD_JPY columns
    """
    print("\n" + "=" * 60)
    print("  Loading Market Data")
    print("=" * 60)
    
    # Fetch all data
    hh = fetch_henry_hub()
    ttf = fetch_ttf()
    jkm = generate_synthetic_jkm(ttf)
    usd_jpy = fetch_usd_jpy()
    
    # Merge all data (aligned by date)
    merged = hh.join(ttf, how="outer")
    merged = merged.join(jkm, how="outer")
    merged = merged.join(usd_jpy, how="outer")
    
    # Forward fill missing values (handle non-trading days)
    merged = merged.ffill().bfill()
    
    # Remove rows with all NaN
    merged = merged.dropna(how="all")
    
    print(f"\n[DataLoader] ✓ Data merge completed, {len(merged)} records total")
    print(f"[DataLoader]   Time range: {merged.index.min().date()} → {merged.index.max().date()}")
    print(f"[DataLoader]   Latest prices: HH=${merged['HH_Price'].iloc[-1]:.2f}, "
          f"TTF=${merged['TTF_Price'].iloc[-1]:.2f}, "
          f"JKM=${merged['JKM_Price'].iloc[-1]:.2f}")
    
    # Save data to CSV
    output_path = os.path.join(config.OUTPUT_DIR, "market_data.csv")
    merged.to_csv(output_path)
    print(f"[DataLoader]   Data saved to {output_path}")
    
    return merged


# =============================================================================
# Internal Helper Functions: Generate Synthetic Data (Fallback)
# =============================================================================

def _fetch_eur_usd(period: str, interval: str) -> pd.DataFrame:
    """Fetch EUR/USD exchange rate for TTF conversion"""
    try:
        ticker = yf.Ticker(config.TICKERS["usd_eur"])
        df = ticker.history(period=period, interval=interval)
        if not df.empty:
            df = df[["Close"]].rename(columns={"Close": "EUR_USD"})
            df.index.name = "Date"
            df.index = df.index.tz_localize(None)
            return df
    except Exception:
        pass
    
    # Fallback: Use fixed exchange rate
    dates = pd.date_range(end=datetime.today(), periods=365, freq="B")
    return pd.DataFrame({"EUR_USD": 1.08}, index=dates)


def _generate_synthetic_henry_hub() -> pd.DataFrame:
    """
    Generate synthetic Henry Hub price data.
    Uses mean reversion + seasonal model, reflecting natural gas price characteristics:
    - Mean around $2.5-3.5/MMBtu
    - Winter (Nov-Mar) prices higher due to heating demand
    - Summer (Jun-Aug) prices also rise slightly due to power generation demand
    """
    np.random.seed(42)
    dates = pd.date_range(end=datetime.today(), periods=252, freq="B")  # ~1 year trading days
    
    # Base price series (mean reversion process Ornstein-Uhlenbeck)
    mean_price = 3.0  # Long-term mean
    speed = 0.03      # Reversion speed
    volatility = 0.08 # Daily volatility
    
    prices = [mean_price]
    for i in range(1, len(dates)):
        # Seasonal adjustment
        month = dates[i].month
        if month in [12, 1, 2]:     # Winter premium
            seasonal = 0.5
        elif month in [7, 8]:        # Summer slight increase
            seasonal = 0.2
        else:
            seasonal = 0.0
        
        # OU process
        dp = speed * (mean_price + seasonal - prices[-1]) + volatility * np.random.randn()
        prices.append(max(prices[-1] + dp, 1.0))  # Price floor $1
    
    df = pd.DataFrame({"HH_Price": prices}, index=dates)
    df.index.name = "Date"
    print(f"[DataLoader] ✓ Generated {len(df)} synthetic Henry Hub data points")
    return df


def _generate_synthetic_ttf() -> pd.DataFrame:
    """
    Generate synthetic TTF price (converted to $/MMBtu).
    TTF is typically higher than Henry Hub, the spread reflects trans-Atlantic shipping costs.
    """
    np.random.seed(123)
    dates = pd.date_range(end=datetime.today(), periods=252, freq="B")
    
    mean_price = 10.0  # TTF mean is higher ($/MMBtu)
    speed = 0.02
    volatility = 0.15
    
    prices = [mean_price]
    for i in range(1, len(dates)):
        month = dates[i].month
        seasonal = 1.5 if month in [11, 12, 1, 2, 3] else 0.0
        dp = speed * (mean_price + seasonal - prices[-1]) + volatility * np.random.randn()
        prices.append(max(prices[-1] + dp, 2.0))
    
    df = pd.DataFrame({"TTF_Price": prices}, index=dates)
    df.index.name = "Date"
    print(f"[DataLoader] ✓ Generated {len(df)} synthetic TTF data points")
    return df


def _generate_synthetic_usd_jpy() -> pd.DataFrame:
    """
    Generate synthetic USD/JPY exchange rate.
    Typical range 140-155, yen has been depreciating in recent years.
    """
    np.random.seed(456)
    dates = pd.date_range(end=datetime.today(), periods=252, freq="B")
    
    mean_rate = 148.0
    speed = 0.01
    volatility = 0.5
    
    rates = [mean_rate]
    for i in range(1, len(dates)):
        dr = speed * (mean_rate - rates[-1]) + volatility * np.random.randn()
        rates.append(max(rates[-1] + dr, 130.0))
    
    df = pd.DataFrame({"USD_JPY": rates}, index=dates)
    df.index.name = "Date"
    print(f"[DataLoader] ✓ Generated {len(df)} synthetic USD/JPY data points")
    return df
