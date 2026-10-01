"""Position sizing and contract math (USD account).

P&L conversion: for USD-quoted instruments (EURUSD, XAUUSD, indices, crypto)
one lot gains `contract_size` USD per 1.0 price move. For USD-base pairs
(USDJPY) the P&L accrues in the quote currency and is converted at the
prevailing price.
"""

from __future__ import annotations

import math
from enum import StrEnum

from pydantic import BaseModel

from market_data.models import AssetSpec


class SizingMethod(StrEnum):
    FIXED_PERCENT = "FIXED_PERCENT"
    FIXED_AMOUNT = "FIXED_AMOUNT"
    VOLATILITY_ADJUSTED = "VOLATILITY_ADJUSTED"


def usd_per_point_per_lot(spec: AssetSpec, price: float) -> float:
    if spec.quote == "USD":
        return spec.contract_size
    if spec.base == "USD" and price > 0:
        return spec.contract_size / price
    return spec.contract_size


def pnl_usd(spec: AssetSpec, direction: int, entry: float, exit_price: float, lots: float) -> float:
    move = direction * (exit_price - entry)
    return move * lots * usd_per_point_per_lot(spec, exit_price)


def notional_usd(spec: AssetSpec, lots: float, price: float) -> float:
    if spec.base == "USD":
        return lots * spec.contract_size
    return lots * spec.contract_size * price


def margin_required(
    spec: AssetSpec, lots: float, price: float, account_max_leverage: float | None = None
) -> float:
    lev = min(spec.max_leverage, account_max_leverage) if account_max_leverage else spec.max_leverage
    return notional_usd(spec, lots, price) / lev


def floor_lots(lots: float, spec: AssetSpec) -> float:
    if lots <= 0:
        return 0.0
    steps = math.floor(lots / spec.lot_step + 1e-9)
    return round(steps * spec.lot_step, 8)


def commission_usd(spec: AssetSpec, lots: float, price: float) -> float:
    """One-side commission."""
    return spec.commission_per_lot * lots + spec.commission_pct * notional_usd(spec, lots, price)


class SizeResult(BaseModel):
    method: SizingMethod
    lots: float
    raw_lots: float
    risk_amount: float
    risk_pct: float
    risk_per_lot: float
    vol_scale: float = 1.0
    notes: list[str] = []


def compute_size(
    *,
    method: SizingMethod,
    equity: float,
    risk_pct: float,
    entry: float,
    stop: float,
    spec: AssetSpec,
    fixed_amount: float | None = None,
    atr_pct: float | None = None,
    atr_pct_reference: float | None = None,
    max_lots: float | None = None,
) -> SizeResult:
    """Lots such that a stop-out loses the budgeted amount (never more)."""
    distance = abs(entry - stop)
    if distance <= 0 or equity <= 0:
        return SizeResult(
            method=method,
            lots=0.0,
            raw_lots=0.0,
            risk_amount=0.0,
            risk_pct=0.0,
            risk_per_lot=0.0,
            notes=["Invalid stop distance or equity"],
        )
    risk_per_lot = distance * usd_per_point_per_lot(spec, stop)
    notes: list[str] = []
    vol_scale = 1.0
    if method == SizingMethod.FIXED_AMOUNT:
        budget = min(fixed_amount or 0.0, equity * risk_pct)
        if fixed_amount and fixed_amount > equity * risk_pct:
            notes.append(f"Fixed amount capped at max risk per trade ({risk_pct:.2%} of equity)")
    elif method == SizingMethod.VOLATILITY_ADJUSTED:
        if atr_pct and atr_pct_reference and atr_pct > 0:
            vol_scale = max(0.5, min(1.0, atr_pct_reference / atr_pct))
            notes.append(
                f"Volatility scale {vol_scale:.2f} (reference ATR% {atr_pct_reference:.3f} / current {atr_pct:.3f})"
            )
        else:
            notes.append("Volatility reference unavailable; using base risk")
        budget = equity * risk_pct * vol_scale
    else:
        budget = equity * risk_pct
    raw = budget / risk_per_lot
    cap = min(spec.max_lot, max_lots) if max_lots else spec.max_lot
    lots = floor_lots(min(raw, cap), spec)
    if raw > cap:
        notes.append(f"Capped at {cap} lots")
    if lots < spec.min_lot:
        notes.append(f"Computed size {raw:.4f} lots is below the minimum lot {spec.min_lot}")
        lots = 0.0
    actual = lots * risk_per_lot
    return SizeResult(
        method=method,
        lots=lots,
        raw_lots=round(raw, 6),
        risk_amount=round(actual, 2),
        risk_pct=round(actual / equity, 6),
        risk_per_lot=round(risk_per_lot, 4),
        vol_scale=round(vol_scale, 3),
        notes=notes,
    )
