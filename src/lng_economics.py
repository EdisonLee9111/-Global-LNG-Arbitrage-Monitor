"""
lng_economics.py - Core LNG Economics Calculation Module
=========================================================
Implements core economic calculations for LNG trading, including:
- Voyage calculation (Voyage Days)
- Boil-off loss (Boil-off Loss)
- Shipping cost (Shipping Cost)
- Netback calculation (Netback Calculation)
- Arbitrage window analysis (Arbitrage Window)

Key Concepts:
- Netback = Destination port selling price - (Shipping cost + Canal fee + Boil-off loss + Liquefaction fee)
- When Netback > Henry Hub → Arbitrage opportunity exists (Open Arb Window)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from . import config


@dataclass
class VoyageResult:
    """Voyage calculation result data class"""
    route_name: str             # Route name
    distance_nm: float          # Distance (nautical miles)
    laden_days: float           # Laden voyage days
    ballast_days: float         # Ballast return days
    total_round_trip_days: float  # Total round trip days
    port_days: float            # Port stay days
    canal: Optional[str]        # Canal passed through
    canal_fee: float            # Canal fee


@dataclass
class ShippingCostResult:
    """Shipping cost calculation result data class"""
    voyage: VoyageResult        # Voyage information
    charter_cost: float         # Charter cost ($/round-trip)
    fuel_cost: float            # Fuel cost ($)
    canal_fee: float            # Canal fee ($)
    boil_off_loss_mmbtu: float  # Boil-off loss (MMBtu)
    boil_off_cost: float        # Boil-off loss cost ($)
    total_cost: float           # Total shipping cost ($)
    cost_per_mmbtu: float       # Unit shipping cost ($/MMBtu)


@dataclass
class NetbackResult:
    """Netback calculation result data class"""
    destination: str            # Destination
    destination_price: float    # Destination port price ($/MMBtu)
    shipping_cost_per_mmbtu: float  # Shipping cost ($/MMBtu)
    liquefaction_cost: float    # Liquefaction fee ($/MMBtu)
    netback: float              # Netback ($/MMBtu)
    henry_hub_price: float      # Current HH price ($/MMBtu)
    arbitrage_spread: float     # Arbitrage spread ($/MMBtu)
    is_arb_open: bool           # Whether arbitrage window is open
    signal: str                 # Trading signal description


class LNGCalculator:
    """
    LNG Economics Calculator
    
    Encapsulates core economic calculation logic for LNG trading,
    used to evaluate arbitrage opportunities across different routes.
    
    Attributes
    ----------
    cargo_size_mmbtu : float
        Cargo size (MMBtu)
    charter_rate : float
        Daily charter rate ($/day)
    fuel_cost_per_day : float
        Daily fuel consumption ($/day)
    liquefaction_cost : float
        Liquefaction fee ($/MMBtu)
    boil_off_rate : float
        Daily evaporation rate
    
    Example
    -------
    >>> calc = LNGCalculator()
    >>> voyage = calc.calculate_voyage("US_Gulf_to_Tokyo_Panama")
    >>> print(f"Voyage days: {voyage.laden_days:.1f} days")
    """
    
    def __init__(
        self,
        cargo_size_mmbtu: float = config.STANDARD_CARGO_SIZE_MMBTU,
        charter_rate: float = config.DEFAULT_CHARTER_RATE,
        fuel_cost_per_day: float = config.DEFAULT_FUEL_COST_PER_DAY,
        liquefaction_cost: float = config.DEFAULT_LIQUEFACTION_COST,
        boil_off_rate: float = config.BOIL_OFF_RATE,
    ):
        self.cargo_size_mmbtu = cargo_size_mmbtu
        self.charter_rate = charter_rate
        self.fuel_cost_per_day = fuel_cost_per_day
        self.liquefaction_cost = liquefaction_cost
        self.boil_off_rate = boil_off_rate
    
    # =========================================================================
    # Core Calculation Methods
    # =========================================================================
    
    def calculate_voyage_days(self, distance_nm: float, speed_knots: float) -> float:
        """
        Calculate voyage days.
        
        Formula: Days = Distance (nautical miles) / (Speed (knots) × 24 hours)
        
        Parameters
        ----------
        distance_nm : float
            Voyage distance (nautical miles, Nautical Miles)
        speed_knots : float
            Vessel speed (knots = nautical miles/hour)
            
        Returns
        -------
        float
            Voyage days
        """
        if speed_knots <= 0:
            raise ValueError("Speed must be positive")
        return distance_nm / (speed_knots * 24.0)
    
    def calculate_boil_off_loss(
        self, 
        volume_mmbtu: float, 
        days: float, 
        boil_off_rate: float = None
    ) -> float:
        """
        Calculate boil-off loss (Boil-off Gas, BOG) during voyage.
        
        LNG is stored in liquid form at -162°C. During transport, heat continuously 
        penetrates the storage tanks, causing a small amount of LNG to evaporate 
        into gaseous methane (BOG).
        
        Physical model: Exponential decay (compound model)
            Remaining volume = V₀ × (1 - r)^d
            Loss volume = V₀ - V₀ × (1 - r)^d = V₀ × [1 - (1 - r)^d]
        
        Where: V₀ = Initial volume, r = Daily evaporation rate, d = Days
        
        Note: Modern LNG vessels can use BOG as main engine fuel (MEGI/X-DF engines),
        so actual "net" loss may be lower than theoretical value. However, in economic 
        accounting, BOG should still be included as opportunity cost.
        
        Parameters
        ----------
        volume_mmbtu : float
            Initial cargo calorific value (MMBtu)
        days : float
            Voyage days
        boil_off_rate : float, optional
            Daily evaporation rate, defaults to value in config
            
        Returns
        -------
        float
            Evaporated loss calorific value (MMBtu)
        """
        rate = boil_off_rate or self.boil_off_rate
        
        # Exponential decay model (compound calculation)
        remaining = volume_mmbtu * (1 - rate) ** days
        loss = volume_mmbtu - remaining
        
        return loss
    
    def calculate_shipping_cost(
        self,
        days_laden: float,
        days_ballast: float,
        port_days: float = None,
        charter_rate: float = None,
        fuel_cost_per_day: float = None,
    ) -> float:
        """
        Calculate total shipping cost (excluding canal fees).
        
        Shipping cost = (Laden days + Ballast days + Port days) × (Daily charter rate + Daily fuel cost)
        
        Note: In practice, the charter market distinguishes between TCE (Time Charter Equivalent) 
        and Spot Charter. Here we use a simplified daily charter model.
        
        Parameters
        ----------
        days_laden : float
            Laden voyage days
        days_ballast : float
            Ballast return days
        port_days : float
            Port operation days
        charter_rate : float
            Daily charter rate ($/day)
        fuel_cost_per_day : float
            Daily fuel cost ($/day)
            
        Returns
        -------
        float
            Total shipping cost ($)
        """
        port_days = port_days or (config.LOADING_TIME + config.UNLOADING_TIME)
        charter = charter_rate or self.charter_rate
        fuel = fuel_cost_per_day or self.fuel_cost_per_day
        
        total_days = days_laden + days_ballast + port_days
        total_cost = total_days * (charter + fuel)
        
        return total_cost
    
    def calculate_voyage(self, route_name: str) -> VoyageResult:
        """
        Calculate complete voyage information.
        
        Parameters
        ----------
        route_name : str
            Route name (must be defined in config.ROUTES)
            
        Returns
        -------
        VoyageResult
            Voyage calculation result
        """
        if route_name not in config.ROUTES:
            raise ValueError(f"Unknown route: {route_name}. Available routes: {list(config.ROUTES.keys())}")
        
        route = config.ROUTES[route_name]
        distance = route["distance_nm"]
        
        # Laden outbound voyage
        laden_days = self.calculate_voyage_days(distance, config.LADEN_SPEED)
        # Ballast return voyage (slightly slower return speed)
        ballast_days = self.calculate_voyage_days(distance, config.BALLAST_SPEED)
        # Port time
        port_days = config.LOADING_TIME + config.UNLOADING_TIME
        
        total_days = laden_days + ballast_days + port_days
        
        return VoyageResult(
            route_name=route_name,
            distance_nm=distance,
            laden_days=laden_days,
            ballast_days=ballast_days,
            total_round_trip_days=total_days,
            port_days=port_days,
            canal=route.get("canal"),
            canal_fee=route.get("canal_fee", 0),
        )
    
    def calculate_full_shipping_cost(self, route_name: str) -> ShippingCostResult:
        """
        Calculate complete shipping cost (including boil-off loss and canal fees).
        
        Complete cost = Charter cost + Fuel cost + Canal fee + Boil-off loss cost
        
        Parameters
        ----------
        route_name : str
            Route name
            
        Returns
        -------
        ShippingCostResult
            Complete shipping cost result
        """
        voyage = self.calculate_voyage(route_name)
        
        # 1) Charter cost + Fuel cost (based on round trip days)
        charter_cost = voyage.total_round_trip_days * self.charter_rate
        fuel_cost = voyage.total_round_trip_days * self.fuel_cost_per_day
        
        # 2) Boil-off loss (only calculate loss for laden outbound voyage)
        boil_off_mmbtu = self.calculate_boil_off_loss(
            self.cargo_size_mmbtu, 
            voyage.laden_days
        )
        # Economic cost of boil-off loss: measured at destination port price (roughly estimated at $10/MMBtu here)
        # Actual netback will use real destination port price
        boil_off_cost_estimate = boil_off_mmbtu * 10.0  # Rough estimate
        
        # 3) Canal fee
        canal_fee = voyage.canal_fee
        
        # 4) Total cost
        total_cost = charter_cost + fuel_cost + canal_fee + boil_off_cost_estimate
        
        # 5) Unit cost ($/MMBtu)
        delivered_volume = self.cargo_size_mmbtu - boil_off_mmbtu
        cost_per_mmbtu = total_cost / delivered_volume if delivered_volume > 0 else float("inf")
        
        return ShippingCostResult(
            voyage=voyage,
            charter_cost=charter_cost,
            fuel_cost=fuel_cost,
            canal_fee=canal_fee,
            boil_off_loss_mmbtu=boil_off_mmbtu,
            boil_off_cost=boil_off_cost_estimate,
            total_cost=total_cost,
            cost_per_mmbtu=cost_per_mmbtu,
        )
    
    def calculate_netback(
        self,
        destination_price: float,
        route_name: str,
        henry_hub_price: float,
        destination_label: str = "",
    ) -> NetbackResult:
        """
        Calculate Netback (netback value) and determine arbitrage window.
        
        Netback formula:
            Netback = Destination port selling price × (1 - BOG loss ratio) 
                      - Shipping cost/unit 
                      - Canal fee/unit 
                      - Liquefaction fee
        
        Arbitrage determination:
            if Netback > Henry Hub Price → Arb Window OPEN ✓
            if Netback ≤ Henry Hub Price → Arb Window CLOSED ✗
        
        Parameters
        ----------
        destination_price : float
            Destination port price ($/MMBtu)
        route_name : str
            Route name
        henry_hub_price : float
            Current Henry Hub price ($/MMBtu)
        destination_label : str
            Destination label (e.g., "Europe (Rotterdam)")
            
        Returns
        -------
        NetbackResult
            Netback analysis result
        """
        voyage = self.calculate_voyage(route_name)
        
        # ---- Boil-off loss ----
        boil_off_mmbtu = self.calculate_boil_off_loss(
            self.cargo_size_mmbtu,
            voyage.laden_days,
        )
        boil_off_ratio = boil_off_mmbtu / self.cargo_size_mmbtu
        delivered_volume = self.cargo_size_mmbtu - boil_off_mmbtu
        
        # ---- Shipping cost (one-way perspective, as Netback focuses on single delivery) ----
        # But in practice, chartering needs to consider round trip, allocated to single cargo
        round_trip_cost = self.calculate_shipping_cost(
            voyage.laden_days, voyage.ballast_days, voyage.port_days
        )
        shipping_per_mmbtu = round_trip_cost / delivered_volume
        
        # ---- Canal fee allocation ----
        canal_per_mmbtu = voyage.canal_fee / delivered_volume if delivered_volume > 0 else 0
        
        # ---- Netback calculation ----
        # Destination port revenue (actual deliverable volume after deducting evaporation × price)
        revenue_per_mmbtu_loaded = destination_price * (1 - boil_off_ratio)
        
        # Netback = Revenue - Shipping cost - Canal fee - Liquefaction fee
        netback = (
            revenue_per_mmbtu_loaded
            - shipping_per_mmbtu
            - canal_per_mmbtu
            - self.liquefaction_cost
        )
        
        # ---- Arbitrage determination ----
        arb_spread = netback - henry_hub_price
        is_open = arb_spread > 0
        
        if is_open:
            if arb_spread > 1.0:
                signal = f"🟢 STRONG BUY: Ample arbitrage space (+${arb_spread:.2f}/MMBtu)"
            else:
                signal = f"🟡 MARGINAL: Narrow arbitrage space (+${arb_spread:.2f}/MMBtu)"
        else:
            signal = f"🔴 NO ARB: Arbitrage window closed ({arb_spread:+.2f}$/MMBtu)"
        
        dest = destination_label or route_name
        
        return NetbackResult(
            destination=dest,
            destination_price=destination_price,
            shipping_cost_per_mmbtu=shipping_per_mmbtu + canal_per_mmbtu,
            liquefaction_cost=self.liquefaction_cost,
            netback=netback,
            henry_hub_price=henry_hub_price,
            arbitrage_spread=arb_spread,
            is_arb_open=is_open,
            signal=signal,
        )
    
    def calculate_historical_netback(
        self,
        market_data: pd.DataFrame,
        route_name: str,
        dest_price_col: str,
        hh_price_col: str = "HH_Price",
    ) -> pd.DataFrame:
        """
        Calculate historical Netback series for time series analysis and visualization.
        
        Parameters
        ----------
        market_data : pd.DataFrame
            Market data (must contain destination port price column and HH price column)
        route_name : str
            Route name
        dest_price_col : str
            Destination port price column name (e.g., 'JKM_Price' or 'TTF_Price')
        hh_price_col : str
            Henry Hub price column name
            
        Returns
        -------
        pd.DataFrame
            DataFrame containing Netback and Arb_Spread columns
        """
        voyage = self.calculate_voyage(route_name)
        boil_off_ratio = self.calculate_boil_off_loss(
            1.0, voyage.laden_days  # Use unit quantity to calculate ratio
        )
        
        delivered_volume = self.cargo_size_mmbtu * (1 - boil_off_ratio)
        round_trip_cost = self.calculate_shipping_cost(
            voyage.laden_days, voyage.ballast_days, voyage.port_days
        )
        shipping_per_mmbtu = round_trip_cost / delivered_volume
        canal_per_mmbtu = voyage.canal_fee / delivered_volume if delivered_volume > 0 else 0
        
        df = market_data[[dest_price_col, hh_price_col]].copy()
        
        # Netback = Destination port price × (1 - BOG ratio) - Shipping cost - Canal fee - Liquefaction fee
        df["Netback"] = (
            df[dest_price_col] * (1 - boil_off_ratio)
            - shipping_per_mmbtu
            - canal_per_mmbtu
            - self.liquefaction_cost
        )
        
        df["Arb_Spread"] = df["Netback"] - df[hh_price_col]
        df["Arb_Open"] = df["Arb_Spread"] > 0
        
        return df
    
    def print_voyage_summary(self, route_name: str) -> None:
        """Print voyage summary"""
        cost = self.calculate_full_shipping_cost(route_name)
        v = cost.voyage
        route_info = config.ROUTES[route_name]
        
        print(f"\n{'─' * 50}")
        print(f"  Route: {route_info['description']}")
        print(f"{'─' * 50}")
        print(f"  Distance:       {v.distance_nm:,.0f} nm")
        print(f"  Laden voyage:   {v.laden_days:.1f} days @ {config.LADEN_SPEED} knots")
        print(f"  Ballast return: {v.ballast_days:.1f} days @ {config.BALLAST_SPEED} knots")
        print(f"  Port time:      {v.port_days:.1f} days")
        print(f"  Total round trip: {v.total_round_trip_days:.1f} days")
        print(f"  Canal:          {v.canal or 'None'}")
        print(f"  ──────────────────────────────────")
        print(f"  Charter cost:   ${cost.charter_cost:,.0f}")
        print(f"  Fuel cost:      ${cost.fuel_cost:,.0f}")
        print(f"  Canal fee:      ${cost.canal_fee:,.0f}")
        print(f"  Boil-off loss:  {cost.boil_off_loss_mmbtu:,.0f} MMBtu "
              f"({cost.boil_off_loss_mmbtu / self.cargo_size_mmbtu * 100:.2f}%)")
        print(f"  ──────────────────────────────────")
        print(f"  Total shipping cost: ${cost.total_cost:,.0f}")
        print(f"  Unit cost:      ${cost.cost_per_mmbtu:.2f}/MMBtu")
