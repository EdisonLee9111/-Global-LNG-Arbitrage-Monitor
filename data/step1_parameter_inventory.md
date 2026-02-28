# Step 1 - Netback Parameter Inventory and Modeling Priority

Objective: Identify the input parameters of the current Netback formula, stratify them by uncertainty and variance contribution, and define the scope for the first version of the model.

## 1) Current Parameter Inventory (Aligned with Code)

| Parameter | Current Code Value | Type | Volatility Characteristics | Worth Modeling? |
|---|---|---|---|---|
| HH Price | `market_data.iloc[-1]["HH_Price"]` in `main.py` (from `data_loader.fetch_henry_hub()`) | Market Risk | Daily volatility, mean-reverting | Required |
| JKM Price | `market_data.iloc[-1]["JKM_Price"]` in `main.py` (synthesized by `generate_synthetic_jkm()`: `TTF + premium + seasonal + noise`) | Market Risk | Daily volatility, strong seasonality | Required |
| TTF Price | `market_data.iloc[-1]["TTF_Price"]` in `main.py` (from `data_loader.fetch_ttf()`) | Market Risk | Daily volatility, pronounced seasonality | Required |
| Charter Rate | `config.DEFAULT_CHARTER_RATE = 60000`, used by `LNGCalculator(charter_rate=...)` | Market Risk | Weekly to monthly volatility, strong seasonality | Required |
| Voyage Days | `distance_nm / speed` (`calculate_voyage_days()`, speed is a config constant) | Operational Risk | Affected by weather, congestion, rerouting | Should |
| BOG Evaporation Rate | `config.BOIL_OFF_RATE = 0.15%/day` | Operational Risk | Vessel-type dependent, small fluctuations | Optional (relatively small impact) |
| Canal Fee | `config.CANAL_FEE_PANAMA = 400000`, `config.CANAL_FEE_SUEZ = 300000` | Structural | Phased adjustments, short-term near-constant | Not modeled for now |
| Liquefaction Cost | `config.DEFAULT_LIQUEFACTION_COST = 3.0` | Contractual | Long-term agreement locked, low-frequency changes | Not modeled for now |
| USD/JPY | `market_data["USD_JPY"]` (from `data_loader.fetch_usd_jpy()`) | Market Risk | Daily volatility, macro-driven | Should (affects Asian buyer behavior) |

## 2) Decision Principles (First Version)

Ranked by variance contribution to `Arb_Spread = Netback - HH`, typically:

1. Price factors (HH/TTF/JKM)
2. Freight factor (Charter)
3. Voyage days
4. Other cost items (BOG, canal fee, liquefaction cost)

Therefore, the first version should model only the 4 required items: `HH`, `TTF`, `JKM`, `charter_rate`. Other parameters remain fixed or use simple range approximations.

## 3) First Version Modeling Boundary (Ready to Execute)

- **Include in stochastic process**: `HH_Price`, `TTF_Price`, `JKM_Price`, `charter_rate`
- **Fixed constants**: `boil_off_rate`, `canal_fee`, `liquefaction_cost`
- **Reserved scenario variables**: `voyage_days`, `USD_JPY` (use upper/lower bound scenarios first, do not enter main stochastic core)

## 4) Interface Recommendations with Existing Code

- Use `market_data` historical series to estimate prices and correlations (HH/TTF/JKM).
- Add injectable parameters at the `LNGCalculator` layer (e.g., scenario-based `charter_rate` and `speed`), maintaining backward compatibility.
- Do not modify the `calculate_netback()` main formula initially; only upgrade inputs from "single-point values" to "scenario values/path values".
