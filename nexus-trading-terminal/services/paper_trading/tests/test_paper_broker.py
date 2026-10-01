from datetime import UTC, datetime, timedelta

import pytest

from market_data.assets import DEFAULT_CATALOG
from market_data.models import Quote
from paper_trading.broker.base import (
    BrokerError,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionStatus,
    TakeProfit,
)
from paper_trading.broker.live import AlpacaBroker, live_trading_gate
from paper_trading.broker.paper import PaperBroker
from paper_trading.broker.store import InMemoryPaperStore
from paper_trading.execution.fills import FillModel
from paper_trading.portfolio.analytics import ClosedTrade, performance_report

SPECS = {a.symbol: a for a in DEFAULT_CATALOG.all()}
T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class Market:
    def __init__(self):
        self.px = {"XAUUSD": 2350.0, "EURUSD": 1.1}
        self.now = T0

    def quote(self, sym):
        p = self.px[sym]
        half = SPECS[sym].typical_spread / 2
        return Quote(symbol=sym, bid=p - half, ask=p + half, price=p, timestamp=self.now, provider="demo", is_demo=True)

    async def source(self, sym):
        return self.quote(sym)

    def all(self):
        return {s: self.quote(s) for s in self.px}


@pytest.fixture
async def env():
    store = InMemoryPaperStore()
    mkt = Market()
    closed = []

    async def on_close(pos, outcome):
        closed.append((pos, outcome))

    await PaperBroker.create_account(store, "acct", "Paper", 100_000, T0)
    broker = PaperBroker(store, "acct", SPECS, mkt.source, FillModel(slippage_bps=0), clock=lambda: mkt.now, on_close=on_close)
    return broker, mkt, closed


async def test_market_order_fills_at_ask_and_charges_nothing_for_gold(env):
    broker, mkt, _ = env
    o = await broker.place_order(OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=1.0, stop_loss=2340.0))
    assert o.status == OrderStatus.FILLED and o.fill_price == pytest.approx(2350.125)
    acct = await broker.get_account()
    assert acct.is_paper and acct.equity == pytest.approx(100_000 + (2349.875 - 2350.125) * 100)
    pos = (await broker.get_positions())[0]
    assert pos.risk_usd == pytest.approx((2350.125 - 2340.0) * 100)


async def test_stop_loss_closes_and_reports_outcome(env):
    broker, mkt, closed = env
    await broker.place_order(OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=1.0, stop_loss=2340.0))
    mkt.now += timedelta(minutes=30)
    mkt.px["XAUUSD"] = 2339.0
    events = await broker.process_quotes(mkt.all())
    assert any(e.type == "STOP_HIT" for e in events)
    pos, outcome = closed[0]
    assert pos.status == PositionStatus.CLOSED and pos.exit_reason == "STOP_LOSS"
    assert outcome.result == "LOSS" and outcome.r_multiple == pytest.approx(pos.realized_pnl / pos.risk_usd, abs=1e-4)
    assert outcome.duration_seconds == pytest.approx(1800)
    assert outcome.mae_r is not None and outcome.mae_r >= 1.0


async def test_partial_take_profit_then_breakeven(env):
    broker, mkt, closed = env
    await broker.place_order(OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=1.0, stop_loss=2340.0,
                                          take_profits=[TakeProfit(price=2360.0, fraction=0.5, label="TP1"),
                                                        TakeProfit(price=2380.0, fraction=0.5, label="TP2")]))
    mkt.px["XAUUSD"] = 2361.0
    ev = await broker.process_quotes(mkt.all())
    assert [e.type for e in ev] == ["TP_HIT"]
    pos = (await broker.get_positions())[0]
    assert pos.lots == pytest.approx(0.5) and pos.stop_loss == pytest.approx(pos.entry_price)
    mkt.px["XAUUSD"] = pos.entry_price - 1
    await broker.process_quotes(mkt.all())
    p, outcome = closed[0]
    assert p.exit_reason == "BREAKEVEN_STOP" and outcome.result == "WIN"


async def test_limit_and_stop_orders_trigger_and_expire(env):
    broker, mkt, _ = env
    lim = await broker.place_order(OrderRequest(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.LIMIT, lots=1.0,
                                                price=1.095, stop_loss=1.09))
    stp = await broker.place_order(OrderRequest(symbol="EURUSD", side=OrderSide.SELL, type=OrderType.STOP, lots=1.0,
                                                price=1.09, stop_loss=1.1, expires_at=T0 + timedelta(minutes=5)))
    assert lim.status == stp.status == OrderStatus.PENDING
    mkt.px["EURUSD"] = 1.0949
    ev = await broker.process_quotes(mkt.all())
    assert any(e.type == "ORDER_FILLED" and e.order_id == lim.id for e in ev)
    mkt.now += timedelta(minutes=10)
    ev = await broker.process_quotes(mkt.all())
    assert any(e.type == "ORDER_EXPIRED" and e.order_id == stp.id for e in ev)
    filled = [o for o in await broker.get_orders() if o.id == lim.id][0]
    assert filled.fill_price <= 1.095


async def test_validation_rejections(env):
    broker, _, _ = env
    bad_lot = await broker.place_order(OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=0.005))
    assert bad_lot.status == OrderStatus.REJECTED
    bad_stop = await broker.place_order(OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=0.1, stop_loss=2400.0))
    assert bad_stop.status == OrderStatus.REJECTED and "Stop" in bad_stop.reject_reason
    huge = await broker.place_order(OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=50.0))
    assert huge.status == OrderStatus.REJECTED and "margin" in huge.reject_reason.lower()
    with pytest.raises(ValueError):
        OrderRequest(symbol="XAUUSD", side=OrderSide.BUY, lots=1, take_profits=[TakeProfit(price=1, fraction=0.7), TakeProfit(price=2, fraction=0.7)])


async def test_kill_switch_blocks_and_cancels(env):
    broker, _, _ = env
    pending = await broker.place_order(OrderRequest(symbol="EURUSD", side=OrderSide.BUY, type=OrderType.LIMIT, lots=1.0, price=1.0))
    cancelled = await broker.set_kill_switch(True)
    assert [o.id for o in cancelled] == [pending.id]
    o = await broker.place_order(OrderRequest(symbol="EURUSD", side=OrderSide.BUY, lots=1.0))
    assert o.status == OrderStatus.REJECTED and "Kill switch" in o.reject_reason
    assert (await broker.get_account()).kill_switch


async def test_manual_and_partial_close(env):
    broker, mkt, closed = env
    await broker.place_order(OrderRequest(symbol="EURUSD", side=OrderSide.SELL, lots=2.0, stop_loss=1.11))
    pos = (await broker.get_positions())[0]
    await broker.close_position(pos.id, lots=0.5)
    pos2 = (await broker.get_positions())[0]
    assert pos2.lots == pytest.approx(1.5)
    with pytest.raises(BrokerError):
        await broker.close_position(pos.id, lots=5)
    mkt.px["EURUSD"] = 1.09
    await broker.close_position(pos.id)
    p, outcome = closed[0]
    assert p.status == PositionStatus.CLOSED and outcome.result == "WIN"
    fills = await broker.store.list_fills("acct")
    assert [f.reason for f in fills] == ["ENTRY", "MANUAL_CLOSE", "MANUAL_CLOSE"]
    assert all(f.is_paper for f in fills)


async def test_live_brokers_cannot_trade_and_gate_is_closed():
    allowed, reasons = live_trading_gate(env_enabled=True, ui_switch_on=True, broker_name="alpaca")
    assert not allowed and any("not implemented" in r for r in reasons)
    allowed, reasons = live_trading_gate(env_enabled=False, ui_switch_on=False, broker_name=None)
    assert not allowed and len(reasons) == 3
    with pytest.raises(BrokerError) as exc:
        await AlpacaBroker().place_order(OrderRequest(symbol="EURUSD", side=OrderSide.BUY, lots=1))
    assert exc.value.code == "BROKER_NOT_IMPLEMENTED"


def test_performance_report():
    rows = [ClosedTrade(closed_at=T0 + timedelta(days=i), symbol="XAUUSD" if i % 2 else "EURUSD", strategy="S",
                        regime="RANGING", pnl=p, r_multiple=p / 100) for i, p in enumerate([100, -100, 250, -100, 50])]
    rep = performance_report(rows)
    assert rep.trades == 5 and rep.total_pnl == 200 and rep.win_rate == pytest.approx(0.6)
    assert rep.max_drawdown == pytest.approx(100)
    assert len(rep.daily) == 5 and {g.key for g in rep.by_asset} == {"XAUUSD", "EURUSD"}
    assert "Small sample" in rep.sample_note
