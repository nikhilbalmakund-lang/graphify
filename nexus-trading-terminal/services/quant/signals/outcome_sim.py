"""Resolve what happened to a signal plan using the candles that FOLLOWED it.

Used to label historical setups and to track live signals. Rules match the
backtester: entry from the bar after the signal, pessimistic stop-first when
a bar touches both stop and target, gaps fill at the open, spread applied,
partial exits per the exit plan with the stop moved to breakeven after TP1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pydantic import BaseModel


class PlanOutcome(BaseModel):
    status: str  # PENDING | ACTIVE | WIN | LOSS | BREAKEVEN | EXPIRED | INVALIDATED
    filled: bool
    fill_index: int | None = None
    fill_time: str | None = None
    fill_price: float | None = None
    exit_time: str | None = None
    exit_reason: str | None = None
    r_multiple: float | None = None
    bars_held: int = 0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    tp_hits: list[str] = []
    tp1_before_sl: bool | None = None
    resolved: bool = False


def simulate_plan(
    future: pd.DataFrame,
    direction: int,
    entry_type: str,
    entry: float,
    stop: float,
    targets: list[tuple[str, float, float]],
    invalidation_level: float | None = None,
    zone: tuple[float, float] | None = None,
    expiry_bars: int = 8,
    max_hold_bars: int = 96,
    spread: float = 0.0,
) -> PlanOutcome:
    """`future` holds only bars strictly after the signal bar. targets: [(label, price, allocation)]."""
    d = direction
    half = spread / 2.0
    o = future["open"].to_numpy(dtype="float64")
    h = future["high"].to_numpy(dtype="float64")
    lo = future["low"].to_numpy(dtype="float64")
    c = future["close"].to_numpy(dtype="float64")
    idx = future.index
    n = len(future)
    fill_i: int | None = None
    fill_px: float | None = None
    for i in range(min(n, expiry_bars)):
        if entry_type == "MARKET":
            fill_i, fill_px = i, o[i] + d * half
            break
        lo_z, hi_z = zone if zone else (entry, entry)
        # Invalidation before fill cancels the setup.
        if invalidation_level is not None and (
            (d > 0 and c[i] < invalidation_level) or (d < 0 and c[i] > invalidation_level)
        ):
            return PlanOutcome(status="INVALIDATED", filled=False, resolved=True, exit_time=str(idx[i]))
        ask_lo, bid_hi = lo[i] + half, h[i] - half
        if d > 0 and ask_lo <= hi_z:
            fill_i, fill_px = i, min(o[i] + half, hi_z)  # limit at zone top; a gap below fills at the open
            break
        if d < 0 and bid_hi >= lo_z:
            fill_i, fill_px = i, max(o[i] - half, lo_z)
            break
    if fill_i is None or fill_px is None:
        if n >= expiry_bars:
            return PlanOutcome(
                status="EXPIRED", filled=False, resolved=True, exit_time=str(idx[expiry_bars - 1])
            )
        return PlanOutcome(status="PENDING", filled=False)
    if (d > 0 and fill_px <= stop) or (d < 0 and fill_px >= stop):
        return PlanOutcome(
            status="LOSS",
            filled=True,
            fill_index=fill_i,
            fill_time=str(idx[fill_i]),
            fill_price=fill_px,
            exit_time=str(idx[fill_i]),
            exit_reason="GAP_THROUGH_STOP",
            r_multiple=-1.0,
            resolved=True,
            tp1_before_sl=False,
        )
    unit = abs(fill_px - stop)
    remaining = 1.0
    realized_r = 0.0
    cur_stop = stop
    pending = list(targets)
    hits: list[str] = []
    best = worst = 0.0
    tp1_first: bool | None = None
    for i in range(fill_i, min(n, fill_i + max_hold_bars)):
        exit_hi, exit_lo = h[i] - d * half, lo[i] - d * half
        fav = (exit_hi - fill_px) * d if d > 0 else (fill_px - exit_lo)
        adv = (fill_px - exit_lo) if d > 0 else (exit_hi - fill_px)
        best, worst = max(best, fav / unit), max(worst, adv / unit)
        stop_hit = (d > 0 and exit_lo <= cur_stop) or (d < 0 and exit_hi >= cur_stop)
        first_tp = pending[0][1] if pending else None
        gap_tp = first_tp is not None and ((d > 0 and o[i] >= first_tp) or (d < 0 and o[i] <= first_tp))
        if stop_hit and not gap_tp:
            px = (
                o[i] - d * half
                if ((d > 0 and o[i] - half <= cur_stop) or (d < 0 and o[i] + half >= cur_stop))
                else cur_stop
            )
            realized_r += remaining * d * (px - fill_px) / unit
            if tp1_first is None:
                tp1_first = False
            reason = "STOP" if cur_stop == stop else "BREAKEVEN_STOP"
            return _final(realized_r, True, fill_i, fill_px, idx, i, reason, best, worst, hits, tp1_first)
        while pending:
            label, tp, alloc = pending[0]
            if (d > 0 and exit_hi >= tp) or (d < 0 and exit_lo <= tp):
                px = max(o[i] - d * half, tp) if d > 0 else min(o[i] - d * half, tp)
                take = min(alloc, remaining)
                realized_r += take * d * (px - fill_px) / unit
                remaining -= take
                hits.append(label)
                pending.pop(0)
                if tp1_first is None:
                    tp1_first = True
                cur_stop = fill_px  # breakeven after the first target
                if remaining <= 1e-9:
                    return _final(
                        realized_r, True, fill_i, fill_px, idx, i, "TARGETS", best, worst, hits, tp1_first
                    )
            else:
                break
        if i - fill_i + 1 >= max_hold_bars:
            realized_r += remaining * d * (c[i] - d * half - fill_px) / unit
            return _final(realized_r, True, fill_i, fill_px, idx, i, "TIME", best, worst, hits, tp1_first)
    return PlanOutcome(
        status="ACTIVE",
        filled=True,
        fill_index=fill_i,
        fill_time=str(idx[fill_i]),
        fill_price=fill_px,
        mfe_r=round(best, 3),
        mae_r=round(worst, 3),
        tp_hits=hits,
        tp1_before_sl=tp1_first,
        bars_held=n - fill_i,
    )


def _final(
    r: float,
    filled: bool,
    fill_i: int,
    fill_px: float,
    idx: pd.Index,
    i: int,
    reason: str,
    best: float,
    worst: float,
    hits: list[str],
    tp1_first: bool | None,
) -> PlanOutcome:
    r = float(np.round(r, 4))
    status = "WIN" if r > 0.05 else "LOSS" if r < -0.05 else "BREAKEVEN"
    return PlanOutcome(
        status=status,
        filled=filled,
        fill_index=fill_i,
        fill_time=str(idx[fill_i]),
        fill_price=fill_px,
        exit_time=str(idx[i]),
        exit_reason=reason,
        r_multiple=r,
        bars_held=i - fill_i + 1,
        mfe_r=round(best, 3),
        mae_r=round(worst, 3),
        tp_hits=hits,
        tp1_before_sl=tp1_first,
        resolved=True,
    )
