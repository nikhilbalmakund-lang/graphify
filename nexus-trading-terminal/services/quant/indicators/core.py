"""Deterministic technical indicators.

All functions are *causal*: the value at bar t depends only on bars <= t, so
the same code is safe for live analysis, backtests and walk-forward tests.
Inputs are pandas Series/DataFrames indexed by time; outputs are aligned
Series (NaN during warm-up). Wilder smoothing is used where it is the
standard definition (RSI, ATR, ADX).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view


def sma(x: pd.Series, n: int) -> pd.Series:
    return x.rolling(n, min_periods=n).mean()


def ema(x: pd.Series, n: int) -> pd.Series:
    return x.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(x: pd.Series, n: int) -> pd.Series:
    """Wilder's moving average (RMA): alpha = 1/n."""
    return x.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = wilder(gain, n)
    avg_loss = wilder(loss, n)
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - 100.0 / (1.0 + rs)
    out = out.where(avg_loss != 0.0, 100.0)
    out = out.where(~((avg_gain == 0.0) & (avg_loss == 0.0)), 50.0)
    return out.where(avg_gain.notna())


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    line = ema(close, fast) - ema(close, slow)
    sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()], axis=1)
    return tr.max(axis=1, skipna=True)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return wilder(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_n = wilder(true_range(df), n)
    plus_di = 100.0 * wilder(plus_dm, n) / tr_n.replace(0.0, np.nan)
    minus_di = 100.0 * wilder(minus_dm, n) / tr_n.replace(0.0, np.nan)
    denom = (plus_di + minus_di).replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / denom
    return pd.DataFrame({"adx": wilder(dx, n), "plus_di": plus_di, "minus_di": minus_di})


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    std = close.rolling(n, min_periods=n).std(ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    width = (upper - lower) / mid
    pct_b = (close - lower) / (upper - lower).replace(0.0, np.nan)
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower, "bb_width": width, "bb_pct_b": pct_b})


def vwap(df: pd.DataFrame, anchor: str = "D", rolling_bars: int | None = None) -> pd.Series:
    """Volume-weighted average price.

    Intraday: anchored to the UTC session day (resets at 00:00 UTC).
    For daily/weekly bars pass `rolling_bars` to get a rolling VWAP instead.
    Returns NaN where cumulative volume is zero (e.g. FX feeds without volume).
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = tp * df["volume"]
    if rolling_bars:
        num = pv.rolling(rolling_bars, min_periods=1).sum()
        den = df["volume"].rolling(rolling_bars, min_periods=1).sum()
    else:
        key = df.index.floor(anchor)
        num = pv.groupby(key).cumsum()
        den = df["volume"].groupby(key).cumsum()
    return num / den.replace(0.0, np.nan)


def stochastic(df: pd.DataFrame, k: int = 14, d: int = 3, smooth: int = 3) -> pd.DataFrame:
    ll = df["low"].rolling(k, min_periods=k).min()
    hh = df["high"].rolling(k, min_periods=k).max()
    raw = 100.0 * (df["close"] - ll) / (hh - ll).replace(0.0, np.nan)
    k_line = raw.rolling(smooth, min_periods=smooth).mean()
    return pd.DataFrame({"stoch_k": k_line, "stoch_d": k_line.rolling(d, min_periods=d).mean()})


def cci(df: pd.DataFrame, n: int = 20) -> pd.Series:
    tp = ((df["high"] + df["low"] + df["close"]) / 3.0).to_numpy(dtype="float64")
    out = np.full(len(tp), np.nan)
    if len(tp) >= n:
        win = sliding_window_view(tp, n)
        mean = win.mean(axis=1)
        md = np.abs(win - mean[:, None]).mean(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[n - 1:] = (tp[n - 1:] - mean) / (0.015 * md)
    return pd.Series(out, index=df.index)


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume).cumsum()


def roc(close: pd.Series, n: int = 10) -> pd.Series:
    return close.pct_change(n) * 100.0


def efficiency_ratio(close: pd.Series, n: int = 20) -> pd.Series:
    """Kaufman efficiency ratio: net move / path length over n bars (0..1)."""
    net = (close - close.shift(n)).abs()
    path = close.diff().abs().rolling(n, min_periods=n).sum()
    return net / path.replace(0.0, np.nan)


def rolling_percentile(x: pd.Series, n: int = 250, min_periods: int = 50) -> pd.Series:
    """Percentile rank (0-100) of the current value within the trailing window (causal).

    Ties count half. NaNs in the window are ignored.
    """
    arr = x.to_numpy(dtype="float64")
    out = np.full(len(arr), np.nan)
    if len(arr) == 0:
        return pd.Series(out, index=x.index)
    padded = np.concatenate([np.full(n - 1, np.nan), arr])
    win = sliding_window_view(padded, n)  # row i == window ending at bar i
    cur = arr[:, None]
    valid = ~np.isnan(win)
    less = np.sum((win < cur) & valid, axis=1)
    equal = np.sum((win == cur) & valid, axis=1)
    count = valid.sum(axis=1)
    ok = (count >= min_periods) & ~np.isnan(arr)
    out[ok] = 100.0 * (less[ok] + 0.5 * equal[ok]) / count[ok]
    return pd.Series(out, index=x.index)


def rolling_autocorr(returns: pd.Series, n: int = 50, lag: int = 1) -> pd.Series:
    return returns.rolling(n, min_periods=n).corr(returns.shift(lag))


def linear_slope(x: pd.Series, n: int = 10) -> pd.Series:
    """Least-squares slope per bar over a trailing window."""
    arr = x.to_numpy(dtype="float64")
    out = np.full(len(arr), np.nan)
    if len(arr) >= n:
        t = np.arange(n) - (n - 1) / 2.0
        denom = float(np.sum(t**2))
        win = sliding_window_view(arr, n)
        out[n - 1:] = (win * t).sum(axis=1) / denom
    return pd.Series(out, index=x.index)
