"""Deterministic scenario engine.

Instead of predicting, describe what would have to happen for each case:
BULLISH (trigger / confirmation / invalidation), BEARISH, and NO-TRADE
conditions, all anchored to measured levels. No probabilities are assigned.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from quant.features.feature_set import FeatureSnapshot
from quant.structure.engine import StructureSnapshot


class ScenarioCase(BaseModel):
    name: str  # BULLISH | BEARISH | NO_TRADE
    trigger: str
    confirmation: str
    invalidation: str
    trigger_level: float | None = None
    invalidation_level: float | None = None
    targets: list[float] = Field(default_factory=list)
    notes: str = ""


class ScenarioSet(BaseModel):
    symbol: str
    timeframe: str
    price: float
    scenarios: list[ScenarioCase]
    basis: str = "Deterministic levels from market structure and ATR; not a forecast"


def build_scenarios(
    symbol: str, timeframe: str, f: FeatureSnapshot, st: StructureSnapshot, prec: int
) -> ScenarioSet:
    price = f.close
    atr = f.atr14 or 0.0
    res = [lv.price for lv in st.resistances]
    sup = [lv.price for lv in st.supports]
    up = res[0] if res else (st.range.high if st.range.high else (price + 1.5 * atr if atr else None))
    dn = sup[0] if sup else (st.range.low if st.range.low else (price - 1.5 * atr if atr else None))
    up2 = res[1] if len(res) > 1 else (up + 2 * atr if up is not None and atr else None)
    dn2 = sup[1] if len(sup) > 1 else (dn - 2 * atr if dn is not None and atr else None)

    def fmt(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.{prec}f}"

    vol_conf = (
        "volume above its 20-bar average"
        if f.volume_available
        else "momentum score turning positive (volume unavailable)"
    )
    vol_conf_dn = (
        "volume above its 20-bar average"
        if f.volume_available
        else "momentum score turning negative (volume unavailable)"
    )
    cases = [
        ScenarioCase(
            name="BULLISH",
            trigger=f"A {timeframe} close above {fmt(up)}",
            confirmation=f"Retest of {fmt(up)} holds with {vol_conf}; RSI stays above 50",
            invalidation=f"Close back below {fmt(dn)}",
            trigger_level=up,
            invalidation_level=dn,
            targets=[x for x in (up2,) if x is not None],
            notes=f"Structure is {st.trend.lower()}; trend score {f.trend_score:.0f}"
            if f.trend_score is not None
            else "",
        ),
        ScenarioCase(
            name="BEARISH",
            trigger=f"A {timeframe} close below {fmt(dn)}",
            confirmation=f"Failed retest of {fmt(dn)} from below with {vol_conf_dn}; RSI stays below 50",
            invalidation=f"Close back above {fmt(up)}",
            trigger_level=dn,
            invalidation_level=up,
            targets=[x for x in (dn2,) if x is not None],
        ),
    ]
    width = (up - dn) / atr if up is not None and dn is not None and atr else None
    nt = []
    if st.range.is_range:
        nt.append(f"price inside the {fmt(st.range.low)}-{fmt(st.range.high)} range")
    if width is not None and width < 2.0:
        nt.append(f"only {width:.1f} ATR between support and resistance (poor reward-to-risk)")
    if f.vol_percentile is not None and f.vol_percentile > 92:
        nt.append("extreme volatility")
    cases.append(
        ScenarioCase(
            name="NO_TRADE",
            trigger="Conditions: "
            + (", ".join(nt) if nt else f"price between {fmt(dn)} and {fmt(up)} without a trigger"),
            confirmation="Stand aside until a bullish or bearish trigger prints",
            invalidation="Either trigger above",
            trigger_level=None,
            invalidation_level=None,
        )
    )
    return ScenarioSet(symbol=symbol, timeframe=timeframe, price=price, scenarios=cases)
