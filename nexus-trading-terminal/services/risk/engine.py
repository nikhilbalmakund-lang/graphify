"""Deterministic risk engine with veto authority.

Every trade - from a signal, the AI analyst, the paper trading UI or a
backtest - passes through `RiskEngine.evaluate`. AI output cannot override
any rule here. The engine also exposes an emergency kill switch state.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from market_data.models import AssetSpec
from risk.sizing import SizingMethod, compute_size, margin_required, notional_usd

RISK_ENGINE_VERSION = "1.0.0"

# Static factor exposures for a LONG position (multiply by direction).
EXPOSURES: dict[str, dict[str, float]] = {
    "XAUUSD": {"USD": -1.0, "METALS": 1.0},
    "EURUSD": {"USD": -1.0, "EUR": 1.0},
    "GBPUSD": {"USD": -1.0, "GBP": 1.0},
    "USDJPY": {"USD": 1.0, "JPY": -1.0},
    "BTCUSD": {"CRYPTO": 1.0, "RISK": 1.0},
    "ETHUSD": {"CRYPTO": 1.0, "RISK": 1.0},
    "NAS100": {"EQUITY": 1.0, "RISK": 1.0},
    "US30": {"EQUITY": 1.0, "RISK": 1.0},
    "SPX500": {"EQUITY": 1.0, "RISK": 1.0},
    "USOIL": {"ENERGY": 1.0},
}


class RiskState(StrEnum):
    NORMAL = "NORMAL"
    RESTRICTED = "RESTRICTED"
    HALTED = "HALTED"


class RiskConfig(BaseModel):
    max_risk_per_trade: float = Field(0.01, gt=0, le=0.05)
    max_daily_loss: float = Field(0.03, gt=0, le=0.2)
    max_weekly_loss: float = Field(0.06, gt=0, le=0.4)
    max_drawdown: float = Field(0.15, gt=0, le=0.6)
    max_open_positions: int = Field(5, ge=1, le=50)
    max_correlated_positions: int = Field(2, ge=1, le=20)
    correlation_threshold: float = Field(0.75, ge=0.3, le=0.99)
    max_leverage: float = Field(10.0, gt=0, le=100)
    max_position_lots: float = Field(10.0, gt=0)
    min_rr: float = Field(1.5, ge=0)
    max_spread_atr: float = Field(0.2, gt=0)
    max_slippage_bps: float = Field(10.0, ge=0)
    news_filter: bool = True
    session_filter: bool = True
    sizing_method: SizingMethod = SizingMethod.FIXED_PERCENT
    fixed_risk_amount: float = Field(500.0, gt=0)


class OpenExposure(BaseModel):
    symbol: str
    direction: int
    lots: float
    entry_price: float
    current_price: float
    stop: float | None = None
    risk_usd: float = 0.0


class AccountState(BaseModel):
    equity: float
    balance: float
    peak_equity: float
    day_start_equity: float
    week_start_equity: float
    open_positions: list[OpenExposure] = Field(default_factory=list)
    kill_switch: bool = False


class TradeProposal(BaseModel):
    symbol: str
    direction: int  # +1 long, -1 short
    entry: float
    stop: float
    effective_rr: float | None = None
    spread: float = 0.0
    atr: float | None = None
    atr_pct: float | None = None
    atr_pct_reference: float | None = None
    market_open: bool = True
    in_news_blackout: bool = False
    expected_slippage_bps: float = 0.0
    requested_lots: float | None = None  # manual orders: validated, never increased
    source: str = "signal"


class RiskCheck(BaseModel):
    name: str
    passed: bool
    detail: str
    value: float | str | None = None
    limit: float | str | None = None


class RiskDecision(BaseModel):
    approved: bool
    state: RiskState
    checks: list[RiskCheck]
    lots: float = 0.0
    risk_amount: float = 0.0
    risk_pct: float = 0.0
    notional: float = 0.0
    margin_required: float = 0.0
    leverage_after: float = 0.0
    sizing_method: SizingMethod
    sizing_notes: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    engine_version: str = RISK_ENGINE_VERSION


class RiskStatus(BaseModel):
    state: RiskState
    kill_switch: bool
    equity: float
    drawdown: float
    daily_pnl: float
    daily_loss_used: float
    weekly_pnl: float
    weekly_loss_used: float
    open_positions: int
    open_risk_usd: float
    gross_exposure: float
    leverage: float
    limits: RiskConfig
    messages: list[str] = Field(default_factory=list)


def correlated(
    sym_a: str,
    dir_a: int,
    sym_b: str,
    dir_b: int,
    corr: dict[tuple[str, str], float] | None = None,
    threshold: float = 0.75,
) -> bool:
    ea, eb = EXPOSURES.get(sym_a, {}), EXPOSURES.get(sym_b, {})
    for factor, va in ea.items():
        vb = eb.get(factor)
        if vb is not None and abs(va) >= 1 and abs(vb) >= 1 and va * dir_a * vb * dir_b > 0:
            return True
    if corr:
        rho = corr.get((sym_a, sym_b), corr.get((sym_b, sym_a)))
        if rho is not None and abs(rho) >= threshold and rho * dir_a * dir_b > 0:
            return True
    return False


class RiskEngine:
    version = RISK_ENGINE_VERSION

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()

    def status(self, acct: AccountState, specs: dict[str, AssetSpec]) -> RiskStatus:
        cfg = self.config
        dd = max(0.0, (acct.peak_equity - acct.equity) / acct.peak_equity) if acct.peak_equity > 0 else 0.0
        daily = acct.equity - acct.day_start_equity
        weekly = acct.equity - acct.week_start_equity
        d_used = (
            max(0.0, -daily) / acct.day_start_equity / cfg.max_daily_loss
            if acct.day_start_equity > 0
            else 0.0
        )
        w_used = (
            max(0.0, -weekly) / acct.week_start_equity / cfg.max_weekly_loss
            if acct.week_start_equity > 0
            else 0.0
        )
        gross = sum(
            notional_usd(specs[p.symbol], p.lots, p.current_price)
            for p in acct.open_positions
            if p.symbol in specs
        )
        msgs: list[str] = []
        state = RiskState.NORMAL
        if acct.kill_switch:
            state = RiskState.HALTED
            msgs.append("Emergency kill switch is active: no new trades")
        if dd >= cfg.max_drawdown:
            state = RiskState.HALTED
            msgs.append(f"Max drawdown reached ({dd:.1%} >= {cfg.max_drawdown:.1%})")
        if d_used >= 1:
            state = RiskState.HALTED
            msgs.append("Daily loss limit reached")
        if w_used >= 1:
            state = RiskState.HALTED
            msgs.append("Weekly loss limit reached")
        if state == RiskState.NORMAL and (d_used >= 0.75 or w_used >= 0.75 or dd >= 0.75 * cfg.max_drawdown):
            state = RiskState.RESTRICTED
            msgs.append("Approaching a loss limit: trading restricted to reduced risk")
        return RiskStatus(
            state=state,
            kill_switch=acct.kill_switch,
            equity=round(acct.equity, 2),
            drawdown=round(dd, 5),
            daily_pnl=round(daily, 2),
            daily_loss_used=round(d_used, 4),
            weekly_pnl=round(weekly, 2),
            weekly_loss_used=round(w_used, 4),
            open_positions=len(acct.open_positions),
            open_risk_usd=round(sum(p.risk_usd for p in acct.open_positions), 2),
            gross_exposure=round(gross, 2),
            leverage=round(gross / acct.equity, 3) if acct.equity > 0 else 0.0,
            limits=cfg,
            messages=msgs,
        )

    def evaluate(
        self,
        prop: TradeProposal,
        acct: AccountState,
        spec: AssetSpec,
        specs: dict[str, AssetSpec],
        corr: dict[tuple[str, str], float] | None = None,
    ) -> RiskDecision:
        cfg = self.config
        st = self.status(acct, specs)
        checks: list[RiskCheck] = []

        def add(
            name: str,
            ok: bool,
            detail: str,
            value: float | str | None = None,
            limit: float | str | None = None,
        ) -> None:
            checks.append(RiskCheck(name=name, passed=ok, detail=detail, value=value, limit=limit))

        add(
            "kill_switch",
            not acct.kill_switch,
            "Kill switch inactive" if not acct.kill_switch else "Kill switch ACTIVE",
        )
        add(
            "max_drawdown",
            st.drawdown < cfg.max_drawdown,
            f"Drawdown {st.drawdown:.2%}",
            st.drawdown,
            cfg.max_drawdown,
        )
        add(
            "max_daily_loss",
            st.daily_loss_used < 1,
            f"Daily loss limit used {st.daily_loss_used:.0%}",
            st.daily_loss_used,
            1.0,
        )
        add(
            "max_weekly_loss",
            st.weekly_loss_used < 1,
            f"Weekly loss limit used {st.weekly_loss_used:.0%}",
            st.weekly_loss_used,
            1.0,
        )
        add(
            "max_open_positions",
            len(acct.open_positions) < cfg.max_open_positions,
            f"{len(acct.open_positions)} open positions",
            len(acct.open_positions),
            cfg.max_open_positions,
        )
        n_corr = sum(
            1
            for p in acct.open_positions
            if correlated(prop.symbol, prop.direction, p.symbol, p.direction, corr, cfg.correlation_threshold)
        )
        add(
            "max_correlated_exposure",
            n_corr < cfg.max_correlated_positions,
            f"{n_corr} correlated open positions in the same direction",
            n_corr,
            cfg.max_correlated_positions,
        )

        stop_ok = (prop.direction > 0 and prop.stop < prop.entry) or (
            prop.direction < 0 and prop.stop > prop.entry
        )
        add(
            "stop_valid",
            stop_ok,
            "Stop is on the losing side of entry" if stop_ok else "Stop is not on the losing side of entry",
        )
        if prop.effective_rr is not None:
            add(
                "min_risk_reward",
                prop.effective_rr >= cfg.min_rr,
                f"R:R {prop.effective_rr:.2f}",
                prop.effective_rr,
                cfg.min_rr,
            )
        if prop.atr and prop.atr > 0:
            ratio = prop.spread / prop.atr
            add(
                "spread_filter",
                ratio <= cfg.max_spread_atr,
                f"Spread {ratio:.3f} ATR",
                round(ratio, 4),
                cfg.max_spread_atr,
            )
        add(
            "slippage_filter",
            prop.expected_slippage_bps <= cfg.max_slippage_bps,
            f"Expected slippage {prop.expected_slippage_bps:.1f} bps",
            prop.expected_slippage_bps,
            cfg.max_slippage_bps,
        )
        if cfg.news_filter:
            add(
                "news_filter",
                not prop.in_news_blackout,
                "No high-impact event blackout"
                if not prop.in_news_blackout
                else "Inside high-impact event blackout",
            )
        if cfg.session_filter:
            add("session_filter", prop.market_open, "Market open" if prop.market_open else "Market closed")

        risk_pct = cfg.max_risk_per_trade * (0.5 if st.state == RiskState.RESTRICTED else 1.0)
        size = compute_size(
            method=cfg.sizing_method,
            equity=acct.equity,
            risk_pct=risk_pct,
            entry=prop.entry,
            stop=prop.stop,
            spec=spec,
            fixed_amount=cfg.fixed_risk_amount,
            atr_pct=prop.atr_pct,
            atr_pct_reference=prop.atr_pct_reference,
            max_lots=cfg.max_position_lots,
        )
        lots = size.lots
        notes = list(size.notes)
        if st.state == RiskState.RESTRICTED:
            notes.append("Risk halved: account is in RESTRICTED state")
        if prop.requested_lots is not None:
            if prop.requested_lots > lots + 1e-12:
                add(
                    "max_risk_per_trade",
                    False,
                    f"Requested {prop.requested_lots} lots exceeds the risk-based maximum of {lots} lots",
                    prop.requested_lots,
                    lots,
                )
            lots = min(lots, prop.requested_lots)

        current_gross = st.gross_exposure
        new_notional = notional_usd(spec, lots, prop.entry)
        max_gross = acct.equity * cfg.max_leverage
        if lots > 0 and current_gross + new_notional > max_gross:
            room = max(0.0, max_gross - current_gross)
            per_lot = notional_usd(spec, 1.0, prop.entry)
            reduced = int(room / per_lot / spec.lot_step) * spec.lot_step if per_lot > 0 else 0.0
            if reduced >= spec.min_lot:
                notes.append(
                    f"Reduced from {lots} to {round(reduced, 8)} lots to respect max leverage {cfg.max_leverage}x"
                )
                lots = round(reduced, 8)
            else:
                lots = 0.0
                add(
                    "max_leverage",
                    False,
                    f"No leverage headroom (gross {current_gross:,.0f} / max {max_gross:,.0f})",
                    round(current_gross / acct.equity, 3),
                    cfg.max_leverage,
                )
        add(
            "position_size",
            lots >= spec.min_lot,
            f"Size {lots} lots" if lots >= spec.min_lot else "Size below the minimum lot",
            lots,
            spec.min_lot,
        )

        risk_amount = lots * size.risk_per_lot
        notional = notional_usd(spec, lots, prop.entry)
        lev_after = (current_gross + notional) / acct.equity if acct.equity > 0 else 0.0
        add(
            "max_risk_per_trade",
            risk_amount <= acct.equity * cfg.max_risk_per_trade * 1.0001,
            f"Risk {risk_amount:,.2f} USD ({risk_amount / acct.equity:.2%})" if acct.equity else "No equity",
            round(risk_amount / acct.equity, 6) if acct.equity else None,
            cfg.max_risk_per_trade,
        )
        if lots > 0:
            add(
                "max_leverage",
                lev_after <= cfg.max_leverage + 1e-9,
                f"Leverage after trade {lev_after:.2f}x",
                round(lev_after, 3),
                cfg.max_leverage,
            )

        failed = [c for c in checks if not c.passed]
        reasons = [f"{c.name}: {c.detail}" for c in failed]
        approved = not failed and lots > 0
        return RiskDecision(
            approved=approved,
            state=st.state,
            checks=checks,
            lots=lots if approved else 0.0,
            risk_amount=round(risk_amount, 2) if approved else 0.0,
            risk_pct=round(risk_amount / acct.equity, 6) if approved and acct.equity else 0.0,
            notional=round(notional, 2) if approved else 0.0,
            margin_required=round(margin_required(spec, lots, prop.entry, cfg.max_leverage), 2)
            if approved
            else 0.0,
            leverage_after=round(lev_after, 3),
            sizing_method=cfg.sizing_method,
            sizing_notes=notes,
            reasons=reasons,
        )
