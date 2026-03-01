# Step 1 Parameter Inventory (Auto Generated)

Goal: classify Netback inputs by uncertainty and modeling priority.

## Parameter Table

| parameter | current_code_value | category | volatility_profile | modeling_priority |
| --- | --- | --- | --- | --- |
| HH price | market_data.iloc[-1]['HH_Price'] -> 3.49 (data_loader.fetch_henry_hub) | Market risk | Daily moves, mean reversion | Must |
| JKM price | market_data.iloc[-1]['JKM_Price'] -> 13.12 (synthetic: TTF + premium + seasonal + noise) | Market risk | Daily moves, strong seasonality | Must |
| TTF price | market_data.iloc[-1]['TTF_Price'] -> 10.55 (data_loader.fetch_ttf) | Market risk | Daily moves | Must |
| Charter rate | config.DEFAULT_CHARTER_RATE = 60,000 USD/day | Market risk | Weekly moves, strong seasonality | Must |
| Fuel cost | config.DEFAULT_FUEL_COST_PER_DAY = 15,000 USD/day (~20% of shipping cost; VLSFO/LSMGO-linked, or correlated with LNG price for MEGI/X-DF vessels) | Market risk | Daily moves, tracks bunker/LNG prices | Should |
| Voyage days | distance_nm / speed in LNGCalculator.calculate_voyage_days (deterministic in current version) | Operational risk | Weather, congestion, rerouting | Should |
| BOG boil-off rate | config.BOIL_OFF_RATE = 0.1500%/day | Operational risk | Vessel-dependent, low variation | Optional |
| Canal fee | Panama=400,000, Suez=300,000 USD | Structural | Mostly stable in short term | Defer |
| Liquefaction fee | config.DEFAULT_LIQUEFACTION_COST = 3.00 USD/MMBtu | Contractual | Long-term contracted | Defer |
| USD/JPY | market_data.iloc[-1]['USD_JPY'] -> 148.56 (data_loader.fetch_usd_jpy) | Market risk | Daily macro-driven moves | Must |

## First Version Modeling Scope

- Must model: HH price, TTF price, JKM price, Charter rate, USD/JPY
- Keep fixed or simple range: Fuel cost, Voyage days, BOG boil-off rate, Canal fee, Liquefaction fee
- Principle: Model inputs with largest spread variance contribution first: prices > freight > FX (USD/JPY affects Asian buyer behavior on US->Asia routes) > voyage days > others
