"""Event-driven, bar-by-bar backtester.

Look-ahead / leakage controls
-----------------------------
* Strategies decide at the CLOSE of bar t using a BarView that cannot read
  bars > t. Indicators and structure are causal (tested).
* Orders created at bar t can only fill from bar t+1 onward:
  MARKET fills at the next bar's open; LIMIT/STOP fill when the next bars'
  range trades through the price (gaps fill at the open, never better).
* Candle prices are treated as mid prices. Buys pay mid + spread/2, sells
  receive mid - spread/2, and every fill pays slippage (bps of price).
* If a stop and a target are both inside the same bar the STOP is assumed to
  have filled first (pessimistic), unless the bar opened beyond the target.
* Higher-timeframe inputs only use HTF bars already closed at bar t.

Survivorship bias: instruments are a fixed user-chosen list, not a filtered
universe, so survivorship selection does not apply. Results on DEMO data are
computed on synthetic prices and say nothing about real markets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, field_validator

from backtesting.metrics.metrics import MetricsBundle, TradeLike, compute_metrics
from backtesting.strategies.base import BarView, SeriesData, Strategy
from market_data.models import AssetSpec
from quant.signals.models import Direction
from risk.sizing import SizingMethod, compute_size, usd_per_point_per_lot

ENGINE_VERSION = "1.0.0"


class BacktestConfig(BaseModel):
    symbol: str
    timeframe: str
    strategy: str
    params: dict[str, Any] = Field(default_factory=dict)
    start: datetime | None = None
    end: datetime | None = None
    initial_capital: float = Field(100_000.0, gt=0)
    risk_per_trade: float = Field(0.01, gt=0, le=0.05)
    spread: float | None = Field(None, ge=0, description="Price units; default = instrument typical spread")
    commission_per_lot: float | None = Field(
        None, ge=0, description="Per side; default = instrument commission"
    )
    commission_pct: float | None = Field(None, ge=0)
    slippage_bps: float = Field(1.0, ge=0, le=100)
    partial_exit_r: float | None = Field(1.0, gt=0)
    partial_fraction: float = Field(0.5, gt=0, lt=1)
    move_stop_to_breakeven: bool = True
    max_bars_in_trade: int | None = Field(100, ge=1)
    order_expiry_bars: int = Field(5, ge=1)
    max_daily_loss: float | None = Field(0.03, gt=0)
    sizing_method: SizingMethod = SizingMethod.FIXED_PERCENT

    @field_validator("end")
    @classmethod
    def _end_after_start(cls, v: datetime | None, info: Any) -> datetime | None:
        start = info.data.get("start")
        if v is not None and start is not None and v <= start:
            raise ValueError("end must be after start")
        return v


class PartialExit(BaseModel):
    time: datetime
    price: float
    lots: float
    pnl: float
    reason: str


class BacktestTrade(TradeLike):
    trade_no: int
    direction: str
    entry_price: float
    exit_price: float
    lots: float
    stop: float
    target: float | None
    fees: float
    slippage_cost: float
    exit_reason: str
    mfe_r: float
    mae_r: float
    strength: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    partial_exits: list[PartialExit] = Field(default_factory=list)


class BacktestResult(BaseModel):
    engine_version: str = ENGINE_VERSION
    strategy: str
    strategy_version: str
    params: dict[str, Any]
    config: BacktestConfig
    data_provider: str
    is_demo: bool
    data_label: str
    bars: int
    trade_start: str | None
    trade_end: str | None
    trades: list[BacktestTrade]
    metrics: MetricsBundle
    equity_curve: list[tuple[str, float]]
    drawdown_curve: list[tuple[str, float]]
    warnings: list[str] = Field(default_factory=list)


@dataclass
class _Order:
    direction: int
    kind: str
    price: float | None
    stop: float
    target: float | None
    lots: float
    created: int
    strength: float
    reasons: list[str]
    regime: str


@dataclass
class _Position:
    direction: int
    entry_idx: int
    entry_price: float
    lots: float
    initial_lots: float
    stop: float
    initial_stop: float
    target: float | None
    risk_usd: float
    fees: float
    slip_cost: float
    regime: str
    strength: float
    reasons: list[str]
    entry_fee: float = 0.0
    realized: float = 0.0
    partial_done: bool = False
    partials: list[PartialExit] = field(default_factory=list)
    best: float = 0.0
    worst: float = 0.0


class Backtester:
    def __init__(
        self,
        data: SeriesData,
        spec: AssetSpec,
        config: BacktestConfig,
        provider: str = "demo",
        is_demo: bool = True,
    ):
        self.d = data
        self.spec = spec
        self.cfg = config
        self.provider = provider
        self.is_demo = is_demo
        self.half_spread = (config.spread if config.spread is not None else spec.typical_spread) / 2.0
        self.comm_lot = (
            config.commission_per_lot if config.commission_per_lot is not None else spec.commission_per_lot
        )
        self.comm_pct = config.commission_pct if config.commission_pct is not None else spec.commission_pct

    # ------------------------------------------------------------- helpers
    def _slip(self, price: float) -> float:
        return price * self.cfg.slippage_bps / 10_000.0

    def _fee(self, lots: float, price: float) -> float:
        notional = lots * self.spec.contract_size * (price if self.spec.base != "USD" else 1.0)
        return self.comm_lot * lots + self.comm_pct * notional

    def _vpp(self, price: float) -> float:
        return usd_per_point_per_lot(self.spec, price)

    def _close_part(self, pos: _Position, lots: float, raw_price: float, t: int, reason: str) -> float:
        """Exit `lots` at a mid/limit price; applies spread, slippage and fees. Returns cash P&L."""
        d = pos.direction
        fill = raw_price - d * self.half_spread - d * self._slip(raw_price)
        pnl = d * (fill - pos.entry_price) * lots * self._vpp(fill)
        fee = self._fee(lots, fill)
        pos.fees += fee
        pos.slip_cost += self._slip(raw_price) * lots * self._vpp(fill)
        pos.lots = round(pos.lots - lots, 10)
        pos.realized += pnl - fee
        pos.partials.append(
            PartialExit(
                time=self.d.df.index[t].to_pydatetime(),
                price=round(fill, 8),
                lots=lots,
                pnl=round(pnl - fee, 2),
                reason=reason,
            )
        )
        return pnl - fee

    # ----------------------------------------------------------------- run
    def run(
        self,
        strategy: Strategy,
        trade_window: tuple[int, int] | None = None,
        start_equity: float | None = None,
    ) -> BacktestResult:
        d, cfg = self.d, self.cfg
        n = len(d)
        idx = d.df.index
        lo_i, hi_i = trade_window or (0, n)
        lo_i = max(lo_i, 0)
        hi_i = min(hi_i, n)
        cash = start_equity if start_equity is not None else cfg.initial_capital
        trades: list[BacktestTrade] = []
        equity_vals: list[float] = []
        in_mkt: list[bool] = []
        pos: _Position | None = None
        order: _Order | None = None
        warnings: list[str] = []
        day_key = None
        day_start_eq = cash
        halted_day = False

        def mark(t: int) -> float:
            if pos is None:
                return cash
            px = d.close[t] - pos.direction * self.half_spread
            return cash + pos.direction * (px - pos.entry_price) * pos.lots * self._vpp(px)

        def finish(t: int, raw_price: float, reason: str) -> None:
            nonlocal pos, cash
            assert pos is not None
            cash += self._close_part(pos, pos.lots, raw_price, t, reason)
            net = pos.realized - pos.entry_fee  # realized is net of exit fees; entry fee was debited at fill
            exits = pos.partials
            total_lots = sum(p.lots for p in exits)
            avg_exit = sum(p.price * p.lots for p in exits) / total_lots if total_lots else raw_price
            r_unit = pos.risk_usd if pos.risk_usd > 0 else np.nan
            trades.append(
                BacktestTrade(
                    trade_no=len(trades) + 1,
                    direction="LONG" if pos.direction > 0 else "SHORT",
                    entry_time=idx[pos.entry_idx].to_pydatetime(),
                    exit_time=idx[t].to_pydatetime(),
                    entry_price=round(pos.entry_price, 8),
                    exit_price=round(avg_exit, 8),
                    lots=pos.initial_lots,
                    stop=round(pos.initial_stop, 8),
                    target=round(pos.target, 8) if pos.target else None,
                    pnl=round(net, 2),
                    pnl_r=round(net / r_unit, 4) if np.isfinite(r_unit) else None,
                    fees=round(pos.fees, 2),
                    slippage_cost=round(pos.slip_cost, 2),
                    bars_held=t - pos.entry_idx,
                    exit_reason=reason,
                    mfe_r=round(pos.best / abs(pos.entry_price - pos.initial_stop), 3),
                    mae_r=round(pos.worst / abs(pos.entry_price - pos.initial_stop), 3),
                    regime=pos.regime,
                    strength=pos.strength,
                    reasons=pos.reasons,
                    partial_exits=exits,
                )
            )
            pos = None

        start_t = max(strategy.min_bars, lo_i)
        for t in range(n):
            if t < lo_i or t >= hi_i:
                if t >= hi_i:
                    break
                continue
            o, h, low, c = d.open[t], d.high[t], d.low[t], d.close[t]
            key = idx[t].date()
            if key != day_key:
                day_key, day_start_eq, halted_day = key, mark(t - 1) if t > 0 else cash, False

            # 1) pending order -> fill
            if order is not None and pos is None:
                fill_mid = None
                if order.kind == "MARKET":
                    fill_mid = o
                elif order.kind == "LIMIT":
                    lim = order.price or o
                    if order.direction > 0 and low + self.half_spread <= lim:
                        fill_mid = min(o + self.half_spread, lim) - self.half_spread
                    elif order.direction < 0 and h - self.half_spread >= lim:
                        fill_mid = max(o - self.half_spread, lim) + self.half_spread
                elif order.kind == "STOP":
                    sp = order.price or o
                    if order.direction > 0 and h + self.half_spread >= sp:
                        fill_mid = max(o + self.half_spread, sp) - self.half_spread
                    elif order.direction < 0 and low - self.half_spread <= sp:
                        fill_mid = min(o - self.half_spread, sp) + self.half_spread
                if fill_mid is not None:
                    dd = order.direction
                    fill = fill_mid + dd * self.half_spread + dd * self._slip(fill_mid)
                    invalid = (dd > 0 and order.stop >= fill) or (dd < 0 and order.stop <= fill)
                    if invalid:
                        warnings.append(
                            f"Order at {idx[t]} skipped: gap moved price through the stop before entry"
                        )
                    else:
                        fee = self._fee(order.lots, fill)
                        cash -= fee
                        risk_usd = abs(fill - order.stop) * order.lots * self._vpp(order.stop)
                        pos = _Position(
                            direction=dd,
                            entry_idx=t,
                            entry_price=fill,
                            lots=order.lots,
                            initial_lots=order.lots,
                            stop=order.stop,
                            initial_stop=order.stop,
                            target=order.target,
                            risk_usd=risk_usd,
                            fees=fee,
                            entry_fee=fee,
                            slip_cost=self._slip(fill_mid) * order.lots * self._vpp(fill),
                            regime=order.regime,
                            strength=order.strength,
                            reasons=order.reasons,
                        )

                    order = None
                elif t - order.created > cfg.order_expiry_bars:
                    order = None

            # 2) manage open position within bar t
            if pos is not None:
                dd = pos.direction
                # bid/ask-adjusted extremes for the exit side
                exit_hi = h - dd * self.half_spread
                exit_lo = low - dd * self.half_spread
                fav = (h - pos.entry_price) if dd > 0 else (pos.entry_price - low)
                adv = (pos.entry_price - low) if dd > 0 else (h - pos.entry_price)
                pos.best, pos.worst = max(pos.best, fav), max(pos.worst, adv)
                stop_hit = (dd > 0 and exit_lo <= pos.stop) or (dd < 0 and exit_hi >= pos.stop)
                risk_px = abs(pos.entry_price - pos.initial_stop)
                partial_px = None
                if cfg.partial_exit_r and not pos.partial_done:
                    partial_px = pos.entry_price + dd * cfg.partial_exit_r * risk_px
                tgt = pos.target
                tgt_hit = tgt is not None and ((dd > 0 and exit_hi >= tgt) or (dd < 0 and exit_lo <= tgt))
                part_hit = partial_px is not None and (
                    (dd > 0 and exit_hi >= partial_px) or (dd < 0 and exit_lo <= partial_px)
                )
                gap_beyond_target = tgt is not None and ((dd > 0 and o >= tgt) or (dd < 0 and o <= tgt))
                if stop_hit and not gap_beyond_target:
                    gap_px = o if ((dd > 0 and o <= pos.stop) or (dd < 0 and o >= pos.stop)) else pos.stop
                    reason = "STOP" if pos.stop == pos.initial_stop else "BREAKEVEN_STOP"
                    finish(t, gap_px, reason)
                else:
                    if part_hit and partial_px is not None:
                        lots_part = max(
                            self.spec.min_lot,
                            round(
                                np.floor(pos.initial_lots * cfg.partial_fraction / self.spec.lot_step)
                                * self.spec.lot_step,
                                8,
                            ),
                        )
                        if lots_part < pos.lots:
                            px = max(o, partial_px) if dd > 0 else min(o, partial_px)
                            cash += self._close_part(pos, lots_part, px, t, "PARTIAL_TP")
                            pos.partial_done = True
                            if cfg.move_stop_to_breakeven:
                                pos.stop = pos.entry_price
                        else:
                            pos.partial_done = True
                    if pos is not None and tgt_hit and tgt is not None:
                        px = max(o, tgt) if dd > 0 else min(o, tgt)
                        finish(t, px, "TARGET")
                    elif (
                        pos is not None
                        and cfg.max_bars_in_trade
                        and t - pos.entry_idx >= cfg.max_bars_in_trade
                    ):
                        finish(t, c, "TIME")

            # 3) decide at the close of bar t
            eq_now = mark(t)
            if (
                cfg.max_daily_loss
                and day_start_eq > 0
                and (day_start_eq - eq_now) / day_start_eq >= cfg.max_daily_loss
            ):
                halted_day = True
            if pos is None and order is None and t >= start_t and t < hi_i - 1 and not halted_day:
                vote = strategy.vote(BarView(d, t))
                if vote.direction != Direction.NO_TRADE and vote.stop is not None:
                    dd = 1 if vote.direction == Direction.LONG else -1
                    ref = vote.entry_price if vote.entry_type in ("LIMIT", "STOP") and vote.entry_price else c
                    atr_ref = None
                    if cfg.sizing_method == SizingMethod.VOLATILITY_ADJUSTED:
                        window = d.cols["atr_pct"][max(0, t - 250) : t + 1]
                        atr_ref = float(np.nanmedian(window)) if np.isfinite(window).any() else None
                    size = compute_size(
                        method=cfg.sizing_method,
                        equity=eq_now,
                        risk_pct=cfg.risk_per_trade,
                        entry=ref + dd * self.half_spread,
                        stop=vote.stop,
                        spec=self.spec,
                        atr_pct=float(d.cols["atr_pct"][t]),
                        atr_pct_reference=atr_ref,
                    )
                    if size.lots >= self.spec.min_lot:
                        order = _Order(
                            direction=dd,
                            kind=vote.entry_type,
                            price=vote.entry_price,
                            stop=vote.stop,
                            target=vote.target,
                            lots=size.lots,
                            created=t,
                            strength=vote.strength,
                            reasons=vote.reasons,
                            regime=str(d.regime_codes[t]),
                        )
            equity_vals.append(mark(t))
            in_mkt.append(pos is not None)

        last = min(hi_i, n) - 1
        if pos is not None and last >= 0:
            finish(last, d.close[last], "END_OF_TEST")
            if equity_vals:
                equity_vals[-1] = cash

        eq_index = idx[lo_i : lo_i + len(equity_vals)]
        equity = pd.Series(equity_vals, index=eq_index, dtype="float64")
        bundle = compute_metrics(trades, equity, in_mkt)
        dd_curve = (equity / equity.cummax() - 1.0) * 100.0 if len(equity) else equity
        step = max(1, len(equity) // 1500)
        if bundle.metrics.total_trades < 30:
            warnings.append(
                f"Only {bundle.metrics.total_trades} trades: statistics are not reliable (small sample)"
            )
        if self.is_demo:
            warnings.append(
                "DEMO DATA: results are computed on synthetic prices and do not describe any real market"
            )
        return BacktestResult(
            strategy=strategy.name,
            strategy_version=strategy.version,
            params=strategy.params,
            config=cfg,
            data_provider=self.provider,
            is_demo=self.is_demo,
            data_label=(
                "DEMO BACKTEST (synthetic data)"
                if self.is_demo
                else f"BACKTEST ({self.provider} historical data)"
            ),
            bars=hi_i - lo_i,
            trade_start=str(idx[lo_i]) if n else None,
            trade_end=str(idx[last]) if n else None,
            trades=trades,
            metrics=bundle,
            equity_curve=[(str(k), round(float(v), 2)) for k, v in equity.iloc[::step].items()],
            drawdown_curve=[(str(k), round(float(v), 3)) for k, v in dd_curve.iloc[::step].items()],
            warnings=warnings,
        )
