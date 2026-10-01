import pytest

from market_data.assets import DEFAULT_CATALOG
from risk.engine import AccountState, OpenExposure, RiskConfig, RiskEngine, RiskState, TradeProposal, correlated
from risk.sizing import SizingMethod, compute_size, floor_lots, pnl_usd, usd_per_point_per_lot

SPECS = {a.symbol: a for a in DEFAULT_CATALOG.all()}


def acct(**kw):
    base = dict(equity=100_000, balance=100_000, peak_equity=100_000, day_start_equity=100_000, week_start_equity=100_000)
    base.update(kw)
    return AccountState(**base)


def gold_long(**kw):
    p = dict(symbol="XAUUSD", direction=1, entry=2350.0, stop=2340.0, effective_rr=2.0, spread=0.25, atr=5.0,
             market_open=True)
    p.update(kw)
    return TradeProposal(**p)


def test_fixed_percent_sizing_never_exceeds_budget():
    spec = SPECS["XAUUSD"]
    r = compute_size(method=SizingMethod.FIXED_PERCENT, equity=100_000, risk_pct=0.01, entry=2350, stop=2340, spec=spec)
    # 1 lot = 100 oz -> $1,000 per $10 stop; budget $1,000 -> 1.0 lot
    assert r.lots == pytest.approx(1.0)
    assert r.risk_amount <= 1000.0 + 1e-6
    r2 = compute_size(method=SizingMethod.FIXED_PERCENT, equity=100_000, risk_pct=0.01, entry=2350, stop=2343, spec=spec)
    assert r2.risk_amount <= 1000.0 and r2.lots == floor_lots(1000 / 700, spec)


def test_usd_base_pair_conversion():
    spec = SPECS["USDJPY"]
    assert usd_per_point_per_lot(spec, 150.0) == pytest.approx(100_000 / 150.0)
    assert pnl_usd(spec, 1, 150.0, 151.0, 1.0) == pytest.approx(100_000 / 151.0)
    r = compute_size(method=SizingMethod.FIXED_PERCENT, equity=50_000, risk_pct=0.01, entry=150.0, stop=149.5, spec=spec)
    assert r.risk_amount <= 500.0 + 1e-6 and r.lots > 0


def test_fixed_amount_capped_and_volatility_adjusted():
    spec = SPECS["EURUSD"]
    r = compute_size(method=SizingMethod.FIXED_AMOUNT, equity=10_000, risk_pct=0.01, entry=1.1, stop=1.098, spec=spec,
                     fixed_amount=5_000)
    assert r.risk_amount <= 100.0 + 1e-6 and r.notes
    hi = compute_size(method=SizingMethod.VOLATILITY_ADJUSTED, equity=100_000, risk_pct=0.01, entry=1.1, stop=1.098,
                      spec=spec, atr_pct=0.4, atr_pct_reference=0.2)
    base = compute_size(method=SizingMethod.FIXED_PERCENT, equity=100_000, risk_pct=0.01, entry=1.1, stop=1.098, spec=spec)
    assert hi.lots < base.lots and hi.vol_scale == pytest.approx(0.5)


def test_below_min_lot_is_rejected():
    r = compute_size(method=SizingMethod.FIXED_PERCENT, equity=100, risk_pct=0.01, entry=2350, stop=2300, spec=SPECS["XAUUSD"])
    assert r.lots == 0.0


def test_approves_clean_trade_and_sizes_it():
    d = RiskEngine().evaluate(gold_long(), acct(), SPECS["XAUUSD"], SPECS)
    assert d.approved and d.lots == pytest.approx(1.0) and d.state == RiskState.NORMAL
    assert d.risk_amount <= 1000.0 + 1e-6


@pytest.mark.parametrize(
    ("overrides", "account", "failed"),
    [
        ({}, {"kill_switch": True}, "kill_switch"),
        ({}, {"equity": 84_000, "peak_equity": 100_000, "day_start_equity": 84_000, "week_start_equity": 84_000}, "max_drawdown"),
        ({}, {"equity": 96_900}, "max_daily_loss"),
        ({"effective_rr": 1.0}, {}, "min_risk_reward"),
        ({"spread": 2.0}, {}, "spread_filter"),
        ({"in_news_blackout": True}, {}, "news_filter"),
        ({"market_open": False}, {}, "session_filter"),
        ({"stop": 2360.0}, {}, "stop_valid"),
        ({"expected_slippage_bps": 50}, {}, "slippage_filter"),
    ],
)
def test_rejections(overrides, account, failed):
    d = RiskEngine().evaluate(gold_long(**overrides), acct(**account), SPECS["XAUUSD"], SPECS)
    assert not d.approved and d.lots == 0
    assert any(c.name == failed and not c.passed for c in d.checks), d.reasons


def test_max_open_and_correlated_positions():
    pos = [OpenExposure(symbol="EURUSD", direction=1, lots=0.1, entry_price=1.1, current_price=1.1),
           OpenExposure(symbol="GBPUSD", direction=1, lots=0.1, entry_price=1.27, current_price=1.27)]
    d = RiskEngine().evaluate(gold_long(), acct(open_positions=pos), SPECS["XAUUSD"], SPECS)
    assert not d.approved and any(c.name == "max_correlated_exposure" and not c.passed for c in d.checks)
    many = [OpenExposure(symbol=s, direction=1, lots=0.1, entry_price=1.0, current_price=1.0) for s in ["NAS100", "USOIL", "BTCUSD", "USDJPY", "SPX500"]]
    d2 = RiskEngine(RiskConfig(max_correlated_positions=10)).evaluate(gold_long(), acct(open_positions=many), SPECS["XAUUSD"], SPECS)
    assert any(c.name == "max_open_positions" and not c.passed for c in d2.checks)


def test_correlation_rules():
    assert correlated("EURUSD", 1, "GBPUSD", 1)
    assert correlated("EURUSD", 1, "USDJPY", -1)  # both short USD
    assert not correlated("EURUSD", 1, "GBPUSD", -1)
    assert correlated("NAS100", 1, "SPX500", 1)
    assert correlated("USOIL", 1, "XAUUSD", 1, corr={("USOIL", "XAUUSD"): 0.8})
    assert not correlated("USOIL", 1, "XAUUSD", 1, corr={("USOIL", "XAUUSD"): 0.2})


def test_manual_requested_lots_cannot_exceed_risk_limit():
    d = RiskEngine().evaluate(gold_long(requested_lots=5.0, effective_rr=None), acct(), SPECS["XAUUSD"], SPECS)
    assert not d.approved and any(c.name == "max_risk_per_trade" and not c.passed for c in d.checks)
    ok = RiskEngine().evaluate(gold_long(requested_lots=0.5, effective_rr=None), acct(), SPECS["XAUUSD"], SPECS)
    assert ok.approved and ok.lots == pytest.approx(0.5)


def test_leverage_cap_reduces_size():
    cfg = RiskConfig(max_leverage=1.0, max_risk_per_trade=0.05)
    d = RiskEngine(cfg).evaluate(gold_long(stop=2349.0), acct(), SPECS["XAUUSD"], SPECS)
    assert d.approved and d.leverage_after <= 1.0 + 1e-9
    assert any("leverage" in n for n in d.sizing_notes)


def test_restricted_state_halves_risk():
    d = RiskEngine().evaluate(gold_long(), acct(equity=97_600), SPECS["XAUUSD"], SPECS)
    assert d.state == RiskState.RESTRICTED and d.approved
    assert d.risk_amount <= 97_600 * 0.005 + 1e-6
