"""
parameter_inventory.py - Step 1 parameter inventory and classification
=====================================================================
Builds a code-driven parameter inventory for the current Netback setup.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List
import os

import pandas as pd

from . import config


@dataclass
class ParameterRow:
    """Single parameter row for Step 1 inventory."""

    parameter: str
    current_code_value: str
    category: str
    volatility_profile: str
    modeling_priority: str


def _build_rows(market_data: pd.DataFrame) -> List[ParameterRow]:
    """Create the parameter rows based on current code and latest data."""
    latest = market_data.iloc[-1]

    hh_val = float(latest["HH_Price"])
    ttf_val = float(latest["TTF_Price"])
    jkm_val = float(latest["JKM_Price"])
    usdjpy_val = float(latest["USD_JPY"])

    rows = [
        ParameterRow(
            parameter="HH price",
            current_code_value=(
                f"market_data.iloc[-1]['HH_Price'] -> {hh_val:.2f} "
                "(data_loader.fetch_henry_hub)"
            ),
            category="Market risk",
            volatility_profile="Daily moves, mean reversion",
            modeling_priority="Must",
        ),
        ParameterRow(
            parameter="JKM price",
            current_code_value=(
                f"market_data.iloc[-1]['JKM_Price'] -> {jkm_val:.2f} "
                "(synthetic: TTF + premium + seasonal + noise)"
            ),
            category="Market risk",
            volatility_profile="Daily moves, strong seasonality",
            modeling_priority="Must",
        ),
        ParameterRow(
            parameter="TTF price",
            current_code_value=(
                f"market_data.iloc[-1]['TTF_Price'] -> {ttf_val:.2f} "
                "(data_loader.fetch_ttf)"
            ),
            category="Market risk",
            volatility_profile="Daily moves",
            modeling_priority="Must",
        ),
        ParameterRow(
            parameter="Charter rate",
            current_code_value=(
                "config.DEFAULT_CHARTER_RATE = "
                f"{config.DEFAULT_CHARTER_RATE:,.0f} USD/day"
            ),
            category="Market risk",
            volatility_profile="Weekly moves, strong seasonality",
            modeling_priority="Must",
        ),
        ParameterRow(
            parameter="Fuel cost",
            current_code_value=(
                "config.DEFAULT_FUEL_COST_PER_DAY = "
                f"{config.DEFAULT_FUEL_COST_PER_DAY:,.0f} USD/day "
                "(~20% of shipping cost; VLSFO/LSMGO-linked, "
                "or correlated with LNG price for MEGI/X-DF vessels)"
            ),
            category="Market risk",
            volatility_profile="Daily moves, tracks bunker/LNG prices",
            modeling_priority="Should",
        ),
        ParameterRow(
            parameter="Voyage days",
            current_code_value=(
                "distance_nm / speed in LNGCalculator.calculate_voyage_days "
                "(deterministic in current version)"
            ),
            category="Operational risk",
            volatility_profile="Weather, congestion, rerouting",
            modeling_priority="Should",
        ),
        ParameterRow(
            parameter="BOG boil-off rate",
            current_code_value=f"config.BOIL_OFF_RATE = {config.BOIL_OFF_RATE:.4%}/day",
            category="Operational risk",
            volatility_profile="Vessel-dependent, low variation",
            modeling_priority="Optional",
        ),
        ParameterRow(
            parameter="Canal fee",
            current_code_value=(
                f"Panama={config.CANAL_FEE_PANAMA:,.0f}, "
                f"Suez={config.CANAL_FEE_SUEZ:,.0f} USD"
            ),
            category="Structural",
            volatility_profile="Mostly stable in short term",
            modeling_priority="Defer",
        ),
        ParameterRow(
            parameter="Liquefaction fee",
            current_code_value=(
                "config.DEFAULT_LIQUEFACTION_COST = "
                f"{config.DEFAULT_LIQUEFACTION_COST:.2f} USD/MMBtu"
            ),
            category="Contractual",
            volatility_profile="Long-term contracted",
            modeling_priority="Defer",
        ),
        ParameterRow(
            parameter="USD/JPY",
            current_code_value=(
                f"market_data.iloc[-1]['USD_JPY'] -> {usdjpy_val:.2f} "
                "(data_loader.fetch_usd_jpy)"
            ),
            category="Market risk",
            volatility_profile="Daily macro-driven moves",
            modeling_priority="Must",
        ),
    ]
    return rows


def _format_markdown_table(df: pd.DataFrame) -> str:
    """Render DataFrame as markdown table without external dependencies."""
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    lines = [header, sep]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    return "\n".join(lines)


def build_step1_inventory(
    market_data: pd.DataFrame,
    output_dir: str = config.OUTPUT_DIR,
) -> Dict[str, object]:
    """
    Build and persist Step 1 inventory outputs.

    Returns
    -------
    dict
        {
            "inventory_df": pd.DataFrame,
            "priority_scope": dict,
            "csv_path": str,
            "md_path": str,
        }
    """
    rows = _build_rows(market_data)
    inventory_df = pd.DataFrame([asdict(r) for r in rows])

    priority_scope = {
        "first_version_model": ["HH price", "TTF price", "JKM price", "Charter rate", "USD/JPY"],
        "fixed_or_range": ["Fuel cost", "Voyage days", "BOG boil-off rate", "Canal fee", "Liquefaction fee"],
        "principle": (
            "Model inputs with largest spread variance contribution first: "
            "prices > freight > FX (USD/JPY affects Asian buyer behavior on US->Asia routes) > voyage days > others"
        ),
    }

    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "step1_parameter_inventory_auto.csv")
    md_path = os.path.join(output_dir, "step1_parameter_inventory_auto.md")

    inventory_df.to_csv(csv_path, index=False)

    md_sections = [
        "# Step 1 Parameter Inventory (Auto Generated)",
        "",
        "Goal: classify Netback inputs by uncertainty and modeling priority.",
        "",
        "## Parameter Table",
        "",
        _format_markdown_table(inventory_df),
        "",
        "## First Version Modeling Scope",
        "",
        f"- Must model: {', '.join(priority_scope['first_version_model'])}",
        f"- Keep fixed or simple range: {', '.join(priority_scope['fixed_or_range'])}",
        f"- Principle: {priority_scope['principle']}",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_sections))

    return {
        "inventory_df": inventory_df,
        "priority_scope": priority_scope,
        "csv_path": csv_path,
        "md_path": md_path,
    }
