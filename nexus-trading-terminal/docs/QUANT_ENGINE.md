# Quant engine

Everything in `services/quant` is deterministic and **causal**: a value at bar *t*
depends only on bars ≤ *t*. The same code serves live analysis, the setup memory,
backtests and walk-forward tests.

## Indicators (`quant/indicators/core.py`)

SMA, EMA, RSI (Wilder), MACD, ATR (Wilder), ADX/±DI, Bollinger Bands (+ width, %B),
VWAP (anchored to the UTC day; rolling on daily bars), Stochastic, CCI, OBV, volume and average volume, ROC,
efficiency ratio, realised volatility and percentile ranks.

## Features (`quant/features/feature_set.py`, `FEATURE_VERSION 1.0.0`)

A versioned snapshot per bar, including distance to VWAP and to EMA20/50/200
(percent and ATR units), ATR %, volatility percentile, Bollinger-width percentile,
volume ratio, momentum score and trend score (−100…+100), prior 20-bar range and
returns. A fixed subset (`SIMILARITY_FEATURES`) forms the similarity vector used by
the setup memory and calibration model.

## Market structure (`quant/structure/engine.py`)

* Swing high/low confirmed after `right` bars (no repainting); swings alternate.
* HH / HL / LH / LL labels; structure trend BULLISH after HH+HL, BEARISH after LH+LL.
* **BOS** (close beyond the last swing in the trend direction) and **CHoCH** (against it).
* Support/resistance from clusters of confirmed swings (0.35 ATR), with touch counts.
* Range (20-bar range ≤ 6 ATR, low efficiency, ADX < 22), breakouts (> 0.1 ATR beyond
  the prior 20-bar extreme), retests and failed breakouts.
* **Heuristic, labelled as such:** liquidity sweeps (wick beyond a swing, close back
  inside) and liquidity zones (equal highs/lows). OHLC data cannot see real orders; the
  UI marks these with `*` and the note "heuristic".

## Regimes (`quant/regime/detector.py`, `REGIME_VERSION 1.0.0`)

TRENDING_BULLISH, TRENDING_BEARISH, RANGING, BREAKOUT, HIGH_VOLATILITY,
LOW_VOLATILITY, MEAN_REVERSION, UNCERTAIN — chosen by fixed priority rules on ADX,
trend score, efficiency ratio, volatility and Bollinger-width percentiles, return
autocorrelation and breakout distance. Each result carries secondary flags, the
evidence values and `clarity` (a rule margin, **not** a probability).

## Multi-timeframe alignment (`quant/mtf/alignment.py`)

Per timeframe (1m…1D): trend, momentum, structure, regime, volatility, RSI, VWAP
relation and nearest levels. Weighted alignment in [−1, 1] (higher timeframes weigh
more). Score adjustment for a direction on the primary timeframe:
`+5 × support − 10 × oppose` over the higher timeframes; a **contradiction** (the two
heaviest higher timeframes both oppose) blocks the signal when
`block_on_mtf_contradiction` is on.

## Scoring (`quant/scoring/scorer.py`)

Each factor gives a directional sub-score *s* ∈ [−1, 1]; points = weight × (s+1)/2.

| Factor | Default weight |
| --- | --- |
| Trend | 20 |
| Market structure | 20 |
| Momentum | 15 |
| Volume / VWAP | 10 |
| Liquidity | 10 |
| Volatility | 10 |
| Macro | 10 |
| Sentiment | 5 |

Weights are configurable (Settings → Signals) and normalised to 100. Every component,
its points and its supporting/opposing notes are stored with the signal. The total is a
**SIGNAL SCORE** — a quality measure, not a probability.

## Levels (`quant/signals/levels.py`)

* **Stop = structural invalidation** (last swing, then mapped S/R) at least
  `min_stop_atr` away incl. a `stop_buffer_atr` buffer, at most `max_stop_atr`.
  No qualifying structure → no stop → **NO_TRADE**. Stops are never invented.
* Entry: MARKET (fresh breakout/sweep or stop already close), otherwise a ZONE/LIMIT
  pull-back (EMA20, broken level, S/R) between stop and price.
* Targets TP1–TP3 from structure (S/R, equal highs/lows, prior-day extremes, swings) at
  ≥ 1R; otherwise explicit R-multiple targets labelled `R-MULTIPLE`.
* Effective R:R weights each target by the exit plan (default 50 / 30 / 20 %).

## Filters (`quant/signals/filters.py`)

Blocking filters (any failure → NO_TRADE): data quality, stale data, market hours,
minimum R:R, stop distance, maximum spread (× ATR), maximum volatility percentile,
news risk (blackout before/after high-impact events), MTF contradiction, level validity
and **insufficient historical evidence** (fewer than `min_historical_samples` similar
setups, optional minimum expectancy). A high score alone never produces a signal.

## Signal engine (`quant/signals/engine.py`, `SIGNAL_ENGINE_VERSION 1.0.0`)

`evaluate()` scores LONG and SHORT, requires `min_score` and a `min_score_margin` over the
other side, builds the plan and runs the filters; `finalize()` adds historical evidence.
Signals expire after `expiry_bars` candles or on invalidation. NO_TRADE is normal.

## Setup memory and calibration (`quant/ml`)

* **Memory:** walks history causally, records every plan the engine would have proposed
  (score ≥ threshold, valid structural stop) and labels it by simulating the following
  candles (`quant/signals/outcome_sim.py`, stop-first). Setups never overlap. Queries
  return k nearest neighbours (same symbol/timeframe/direction, regime-aware) with sample
  size labels: NONE, INSUFFICIENT (< 10), SMALL (< 30), MODERATE (< 100), LARGE.
* **Calibration:** logistic regression + isotonic calibration for "TP1 before stop",
  time-ordered 60/20/20 split, HistGradientBoosting challenger. Shown as a probability
  **only if** the untouched test split has n ≥ 100, ECE ≤ 0.05 and positive Brier skill.

## Scenarios (`quant/signals/scenarios.py`)

Deterministic BULLISH / BEARISH / NO-TRADE scenarios with trigger, confirmation and
invalidation levels from structure — used by the research workspace instead of
predictions.
