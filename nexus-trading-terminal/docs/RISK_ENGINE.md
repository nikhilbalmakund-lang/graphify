# Risk engine

`services/risk/engine.py` (`RISK_ENGINE_VERSION 1.0.0`) is deterministic and has the
**final veto** over every order: manual paper orders, signal executions and automatic
paper execution. AI output never reaches it except through an already-downgraded signal.

## State

Computed from the paper account: equity, peak equity, day/week start equity, open
positions with risk and notional, kill switch. States:

* **NORMAL** — all limits respected.
* **RESTRICTED** — 75 % or more of the daily-loss, weekly-loss or drawdown limit used (warnings shown; new risk still checked).
* **HALTED** — kill switch on, or daily loss, weekly loss or max drawdown breached.

## Checks (all reported with value and limit)

| Check | Default |
| --- | --- |
| `kill_switch` | must be off |
| `max_drawdown` | 15 % from peak equity |
| `max_daily_loss` | 3 % of day-start equity |
| `max_weekly_loss` | 6 % of week-start equity |
| `max_open_positions` | 5 |
| `max_correlated_exposure` | ≤ 2 same-direction positions with correlation ≥ 0.75 |
| `stop_valid` | a stop on the correct side of entry |
| `min_risk_reward` | 1.5 (effective, exit-plan weighted) |
| `spread_filter` | spread ≤ 0.2 × ATR |
| `slippage_filter` | expected slippage ≤ 10 bps |
| `news_filter` | no high-impact event blackout for the instrument's currencies |
| `session_filter` | market open |
| `max_risk_per_trade` | 1 % of equity (hard cap 5 %) |
| `max_leverage` | 10× after the trade |
| `position_size` | ≥ minimum lot, ≤ `max_position_lots` |

## Position sizing (`services/risk/sizing.py`)

* **FIXED_PERCENT** — risk = equity × risk %; lots = risk / (stop distance × USD per point per lot).
* **FIXED_AMOUNT** — fixed USD risk per trade.
* **VOLATILITY_ADJUSTED** — scales the risk budget by reference ATR % / current ATR %, clamped to 0.5–1.0 (never above the base risk).

Lots are rounded down to the instrument's lot step and never exceed the lots requested
for a manual order. If the leverage limit binds, size is reduced to fit; if even the
minimum lot does not fit, the order is rejected with the reason.

## Kill switch

`POST /api/paper-trading/kill-switch {"active": true}` (or the button on Paper Trading)
cancels all pending paper orders and makes every subsequent risk check fail until it is
released. Open positions stay open for manual management.

## Live trading

Live execution needs three independent gates: `LIVE_TRADING_ENABLED=true` on the
server, the UI safety switch, and an implemented live broker adapter. The adapters in
`paper_trading/broker/live.py` (MT5, IBKR, Alpaca) are documented stubs that refuse to
place orders, so live execution cannot be armed in this build. The kill switch overrides
everything.
