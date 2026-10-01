"""Read-only tools exposed to the AI analyst.

Every tool only READS data or runs a deterministic calculation. There is no
order-placement tool; the AI cannot trade, modify records or bypass risk
controls. Tool results follow one contract:
{"summary": str, "facts": [str], "calculations": [str], "data": {...}}.
"""

from __future__ import annotations

from ai.providers.base import ToolSpec

SYMBOL = {"type": "string", "description": "Instrument symbol, e.g. XAUUSD, EURUSD, BTCUSD, NAS100"}
TIMEFRAME = {
    "type": "string",
    "enum": ["1m", "5m", "15m", "30m", "1H", "4H", "1D"],
    "description": "Chart timeframe",
}


def _obj(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_market_data",
        description="Latest quote, 24h change, market status and data mode (LIVE/DEMO) for a symbol.",
        parameters=_obj({"symbol": SYMBOL}, ["symbol"]),
    ),
    ToolSpec(
        name="get_indicators",
        description="Deterministic indicators and derived features for a symbol/timeframe.",
        parameters=_obj({"symbol": SYMBOL, "timeframe": TIMEFRAME}, ["symbol", "timeframe"]),
    ),
    ToolSpec(
        name="get_structure",
        description="Market structure: trend, swings, BOS/CHoCH, support/resistance, regime, multi-timeframe alignment.",
        parameters=_obj({"symbol": SYMBOL, "timeframe": TIMEFRAME}, ["symbol", "timeframe"]),
    ),
    ToolSpec(
        name="get_news",
        description="Recent normalized news items with source attribution and sentiment.",
        parameters=_obj(
            {
                "symbol": {"type": "string", "description": "Optional symbol filter"},
                "limit": {"type": "integer", "description": "Max items (1-20)"},
            },
            [],
        ),
    ),
    ToolSpec(
        name="get_calendar",
        description="Upcoming economic calendar events with impact levels.",
        parameters=_obj(
            {
                "currency": {"type": "string", "description": "Optional currency filter, e.g. USD"},
                "hours_ahead": {"type": "integer", "description": "Look-ahead window in hours (1-168)"},
            },
            [],
        ),
    ),
    ToolSpec(
        name="get_historical_setups",
        description="Outcomes of historically similar setups (sample size, win rate, average R).",
        parameters=_obj(
            {
                "symbol": SYMBOL,
                "timeframe": TIMEFRAME,
                "k": {"type": "integer", "description": "Number of similar setups (10-100)"},
            },
            ["symbol", "timeframe"],
        ),
    ),
    ToolSpec(
        name="get_portfolio",
        description="Paper trading account, open positions and exposure (SIMULATED).",
        parameters=_obj({}, []),
    ),
    ToolSpec(
        name="get_risk_status",
        description="Risk engine state, limits and current usage.",
        parameters=_obj({}, []),
    ),
    ToolSpec(
        name="calculate_signal",
        description="Run the deterministic signal engine (no AI) and return the result.",
        parameters=_obj({"symbol": SYMBOL, "timeframe": TIMEFRAME}, ["symbol", "timeframe"]),
    ),
    ToolSpec(
        name="calculate_position_size",
        description="Risk-engine position size for a hypothetical entry/stop. Does not place an order.",
        parameters=_obj(
            {
                "symbol": SYMBOL,
                "direction": {"type": "string", "enum": ["LONG", "SHORT"]},
                "entry": {"type": "number"},
                "stop": {"type": "number"},
            },
            ["symbol", "direction", "entry", "stop"],
        ),
    ),
]

TOOL_NAMES = {t.name for t in TOOLS}
FORBIDDEN_TOOLS = {"place_order", "cancel_order", "close_position", "modify_order", "update_settings"}
if TOOL_NAMES & FORBIDDEN_TOOLS:  # explicit check: survives `python -O`
    raise RuntimeError("Execution tools must never be exposed to AI")
