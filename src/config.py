"""
config.py - Global LNG Arbitrage Monitor Configuration File
===========================================================
Contains physical constants, shipping parameters, geographic distances, and 
market data configurations required for energy trading.
These parameters reflect professional domain knowledge of the LNG industry.
"""

# =============================================================================
# 1. Physical Conversion Constants
# =============================================================================

# 1 MMBtu = 0.29307 MWh (Million British Thermal Units -> Megawatt-hours)
MMBTU_TO_MWH = 0.29307

# 1 ton LNG ≈ 52 MMBtu (depends on LNG composition, Lean Gas with ~95% methane)
# Note: Rich Gas (with more ethane/propane) has higher calorific value, ~54 MMBtu/ton
TON_TO_MMBTU = 52.0

# 1 cubic meter LNG ≈ 600 standard cubic meters of natural gas
LNG_DENSITY = 0.45  # tons/cubic meter (average LNG density)

# Standard LNG vessel cargo capacity (typical Q-Flex vessel)
STANDARD_CARGO_SIZE_CBM = 160000    # cubic meters
STANDARD_CARGO_SIZE_TONS = STANDARD_CARGO_SIZE_CBM * LNG_DENSITY  # ≈ 72,000 tons
STANDARD_CARGO_SIZE_MMBTU = STANDARD_CARGO_SIZE_TONS * TON_TO_MMBTU  # ≈ 3,744,000 MMBtu


# =============================================================================
# 2. Shipping Parameters
# =============================================================================

# Vessel speed (knots)
LADEN_SPEED = 17.0     # Laden voyage speed
BALLAST_SPEED = 16.0   # Ballast voyage speed

# Boil-off Rate (BOG evaporation rate)
# LNG naturally evaporates during transport due to heat ingress, typical value is 0.10%-0.15% per day
# Modern MEGI/X-DF engines can use BOG as fuel, reducing net loss
BOIL_OFF_RATE = 0.15 / 100  # Daily evaporation rate 0.15% (conservative estimate)

# Port operation time (days)
LOADING_TIME = 1.5     # Loading time
UNLOADING_TIME = 2.0   # Unloading time

# Canal transit fees (USD)
CANAL_FEE_PANAMA = 400_000   # Panama Canal fee (typical LNG vessel)
CANAL_FEE_SUEZ = 300_000     # Suez Canal fee

# Default charter rate and fuel costs
DEFAULT_CHARTER_RATE = 60_000       # Daily charter rate $/day (TCE, Time Charter Equivalent)
DEFAULT_FUEL_COST_PER_DAY = 15_000  # Daily fuel consumption $/day (VLSFO or LNG as fuel)

# Liquefaction fee (Liquefaction Tolling Fee)
DEFAULT_LIQUEFACTION_COST = 3.0     # $/MMBtu (typical US Gulf Coast rate)


# =============================================================================
# 3. Geographic Distances (Nautical Miles between Key LNG Routes)
# =============================================================================

ROUTES = {
    # ========== From US Gulf Coast (Sabine Pass, LA) ==========
    "US_Gulf_to_Tokyo_Panama": {
        "distance_nm": 9_200,      # Via Panama Canal to Tokyo Bay
        "canal": "Panama",
        "canal_fee": CANAL_FEE_PANAMA,
        "description": "Sabine Pass → Panama Canal → Tokyo Bay"
    },
    "US_Gulf_to_Tokyo_COGH": {
        "distance_nm": 14_500,     # Via Cape of Good Hope to Tokyo Bay
        "canal": None,
        "canal_fee": 0,
        "description": "Sabine Pass → Cape of Good Hope → Tokyo Bay"
    },
    "US_Gulf_to_Rotterdam": {
        "distance_nm": 5_000,      # To Rotterdam (core European hub)
        "canal": None,
        "canal_fee": 0,
        "description": "Sabine Pass → Rotterdam (NW Europe)"
    },
    "US_Gulf_to_Shanghai_Panama": {
        "distance_nm": 10_500,     # Via Panama Canal to Shanghai
        "canal": "Panama",
        "canal_fee": CANAL_FEE_PANAMA,
        "description": "Sabine Pass → Panama Canal → Shanghai"
    },

    # ========== Other Important Routes (Backup) ==========
    "Qatar_to_Tokyo_Suez": {
        "distance_nm": 6_500,      # Qatar via Suez to Japan
        "canal": "Suez",
        "canal_fee": CANAL_FEE_SUEZ,
        "description": "Ras Laffan → Suez Canal → Tokyo Bay"
    },
    "Qatar_to_Rotterdam_Suez": {
        "distance_nm": 6_300,      # Qatar via Suez to Europe
        "canal": "Suez",
        "canal_fee": CANAL_FEE_SUEZ,
        "description": "Ras Laffan → Suez Canal → Rotterdam"
    },
}


# =============================================================================
# 4. Market Data Tickers (Yahoo Finance)
# =============================================================================

TICKERS = {
    "henry_hub": "NG=F",       # NYMEX Henry Hub Natural Gas Futures
    "ttf": "TTF=F",            # ICE TTF Natural Gas Futures (EUR/MWh)
    "usd_jpy": "JPY=X",       # USD/JPY exchange rate
    "usd_eur": "EURUSD=X",    # EUR/USD exchange rate
}

# JKM (Japan Korea Marker) Data Note:
# JKM is the LNG spot benchmark price published by S&P Global Platts ($/MMBtu)
# This is paid data, this project uses TTF + premium method to generate synthetic data
JKM_PREMIUM_OVER_TTF = 1.5  # Typical Asian premium of JKM relative to TTF ($/MMBtu)

# Data retrieval time range
DATA_PERIOD = "1y"   # Last 1 year
DATA_INTERVAL = "1d"  # Daily frequency data


# =============================================================================
# 5. NLP Sentiment Analysis Configuration
# =============================================================================

# Sample central bank meeting minutes text (for demonstration)
SAMPLE_FED_MINUTES = """
The Committee decided to maintain the target range for the federal funds rate 
at 5-1/4 to 5-1/2 percent. In considering any adjustments to the target range, 
the Committee will carefully assess incoming data, the evolving outlook, and 
the balance of risks. The Committee does not expect it will be appropriate to 
reduce the target range until it has gained greater confidence that inflation 
is moving sustainably toward 2 percent. In addition, the Committee will continue 
reducing its holdings of Treasury securities and agency debt and agency 
mortgage-backed securities. The Committee is strongly committed to returning 
inflation to its 2 percent objective. Recent indicators suggest that economic 
activity has been expanding at a solid pace. Job gains have moderated but 
remain strong, and the unemployment rate has remained low. Inflation has eased 
over the past year but remains elevated. The economic outlook is uncertain, 
and the Committee remains highly attentive to inflation risks. Financial 
conditions have tightened considerably, which is likely to weigh on economic 
activity, hiring, and inflation. The Committee will take into account the 
cumulative tightening of monetary policy, the lags with which monetary policy 
affects economic activity and inflation, and economic and financial developments.
"""

SAMPLE_BOJ_MINUTES = """
The Bank of Japan decided to maintain its yield curve control framework and 
keep short-term interest rates at minus 0.1 percent. The Bank will continue 
to purchase Japanese government bonds so that 10-year JGB yields will remain 
at around zero percent. Japan's economy has recovered moderately although some 
weakness has been seen in part. Exports and industrial production have been 
relatively flat. The year-on-year rate of change in the consumer price index 
(CPI, all items less fresh food) has been in the range of 2.5-3.0 percent. 
Inflation expectations have risen moderately. The Bank needs to patiently 
continue with monetary easing under yield curve control. If necessary, the 
Bank will take additional easing measures. The Bank will closely monitor 
developments in financial and foreign exchange markets and their impact on 
Japan's economic activity and prices. The yen depreciation has pushed up 
import prices significantly, contributing to cost-push inflation. The Bank 
recognizes the need to watch for potential side effects of prolonged monetary 
easing. Wage growth has shown signs of acceleration, but sustainable and 
stable achievement of the 2 percent price stability target is not yet in sight.
"""

# Hawkish/Dovish keyword dictionary (for enhanced sentiment analysis)
HAWKISH_KEYWORDS = [
    "tightening", "hawkish", "rate hike", "inflation risk", "overheating",
    "restrictive", "reduce holdings", "tapering", "strongly committed",
    "elevated inflation", "price stability", "vigilant", "normalizing"
]

DOVISH_KEYWORDS = [
    "easing", "dovish", "rate cut", "accommodative", "stimulus",
    "support growth", "employment", "patience", "downside risk",
    "additional easing", "patiently continue", "uncertainty",
    "weakness", "monetary easing"
]


# =============================================================================
# 6. JERA / Japan Domestic Market Configuration
# =============================================================================

# Japanese regulated gas tariff revenue (JPY per MMBtu)
# Represents the approximate blended revenue a Japanese utility earns
# from selling regasified LNG into the domestic gas/power grid.
# When Import_Cost_JPY (= JKM_USD × USD/JPY) exceeds this level,
# JERA would prefer to divert the cargo to the spot market rather
# than import at a loss.
JERA_DOMESTIC_REVENUE_JPY = 1500.0  # JPY/MMBtu (conservative estimate)


# =============================================================================
# 7. Output Configuration
# =============================================================================

OUTPUT_DIR = "data"  # Chart and data output directory
FIGURE_DPI = 150     # Output chart resolution
