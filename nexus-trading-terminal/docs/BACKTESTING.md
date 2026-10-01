# Backtesting

`services/backtesting` — strategies, an event-driven engine (`ENGINE_VERSION 1.0.0`),
metrics and walk-forward validation. UI: **Backtesting** and **Strategy Lab** pages.
API: `POST /api/backtests`, `POST /api/backtests/walk-forward`.

## Strategies (`backtesting/strategies/library.py`)

| Strategy | Idea | Active regimes |
| --- | --- | --- |
| TrendFollowing | EMA20/EMA50 trend with ADX filter; pull-back to EMA20 that closes back in trend | trending, breakout |
| VWAPMomentum | VWAP reclaim/loss with rising MACD histogram, RSI momentum band, above-average volume | trending, breakout, uncertain, high volatility |
| Breakout | Close beyond the prior 20-bar range after a volatility squeeze; measured-move target | squeeze / breakout |
| MeanReversion | In low-ADX ranges, fade a Bollinger excursion once price closes back inside; target mid-band | ranging, mean reversion, low volatility |
| MarketStructure | After BOS/CHoCH, enter on a retest of the broken level that holds; stop beyond the last swing | trending, breakout, uncertain |
| MultiTimeframeConfluence | Higher timeframe and primary trend agree; enter when momentum turns in that direction | trending, breakout |

Each strategy has a version, defaults and a parameter grid (for walk-forward). Live
signals record an ensemble vote of all strategies (`backtesting/strategies/ensemble.py`):
strategies only vote in regimes they are designed for, weighted by their measured
performance in that regime.

## Engine rules (no look-ahead, no leakage)

* Strategies decide at the **close of bar t** through a `BarView` that raises
  `LookAheadError` on any access to bars > t. Indicators and structure are causal.
* Orders created at t fill from t+1: MARKET at the next open; LIMIT/STOP when the range
  trades through the price; gaps fill at the open, never better. Unfilled orders expire
  after `order_expiry_bars`.
* Candles are treated as mid prices: buys pay +spread/2, sells −spread/2; every fill pays
  slippage (bps) and commission (per lot and/or %).
* If stop and target are both inside one bar the **stop fills first** (pessimistic)
  unless the bar opened beyond the target.
* Partial exit at a configurable R (default 50 % at 1R), optional move to breakeven,
  maximum bars in trade, daily loss stop, fixed-%, fixed-$ or volatility-adjusted sizing.
* Higher-timeframe inputs use only HTF bars already closed at t.
* Survivorship bias does not apply: the instrument list is fixed by the user.

## Metrics (`backtesting/metrics/metrics.py`)

Total trades, wins, losses, breakeven, win rate, profit factor, expectancy ($ and R),
average R, average win/loss, net profit, total return, max drawdown (% and $), Sharpe,
Sortino, CAGR, volatility, exposure, largest win/loss, longest winning/losing streak,
average bars held; plus monthly returns, **every losing period** (start, trough,
recovery or "not recovered", depth, duration), results by regime and the R distribution.
Nothing is hidden or smoothed; charts decimate long curves while preserving extremes.

## Walk-forward (`backtesting/validation/walk_forward.py`)

```
| TRAIN (choose params) | VALIDATION (confirm) | TEST (report) |  → roll forward by TEST length
```

For each window the parameter grid is evaluated on TRAIN, the best candidate is
confirmed on VALIDATION, and results are reported on the untouched TEST segment. The
stitched out-of-sample TEST results produce the headline metrics and equity curve.
The UI shows each window's exact dates, chosen parameters and train/validation/test
expectancy.

### Overfitting checks (`backtesting/validation/overfitting.py`)

`TOO_FEW_TRADES`, `TRAIN_TEST_GAP` (in-sample much better than out-of-sample),
`POOR_OUT_OF_SAMPLE`, `UNSTABLE_RESULTS` (windows disagree), `PARAMETER_SENSITIVITY`
(neighbouring parameters collapse), `EXTREME_OPTIMIZATION` (best candidate is an outlier).
A CRITICAL flag, or three or more flags, marks the run as suspicious.

## Data sources

* **provider** — the configured market data provider (DEMO synthetic data without keys;
  every result is then labelled "DEMO BACKTEST (synthetic data)").
* **imported:&lt;batch&gt;** — a validated CSV imported on the Markets page
  (`timestamp, open, high, low, close, volume`; invalid rows reject the whole file).

Backtest results by regime feed `strategy_regime_stats`, which the ensemble uses.
Backtests describe the past on the given data only; they are not predictions.
