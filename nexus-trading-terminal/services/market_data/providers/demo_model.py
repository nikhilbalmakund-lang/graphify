"""Deterministic synthetic price model used ONLY in DEMO MODE.

Design goals
------------
* Deterministic: the same (symbol, timestamp) always yields the same price on
  every machine, so tests, seeds and screenshots are reproducible.
* Consistent across timeframes: every timeframe is aggregated from one
  underlying 1-minute path, so 15m / 1H / 4H / 1D candles agree.
* Realistic *structure* (trends, ranges, volatility clusters, session
  seasonality, weekend gaps) so the quant engine has something meaningful to
  analyse. The output is still synthetic and must always be labelled DEMO.

Construction
------------
1. A daily log-price path is generated once per symbol from a fixed epoch with
   a regime-switching process (trend-up / trend-down / range / volatile /
   quiet blocks) plus a weak long-run pull towards an anchor level so prices
   stay in a plausible band.
2. Within each day a 1440-minute path is drawn and bridged so that it ends
   exactly at that day's close. Minute paths are generated lazily per day with
   a counter-based seed and cached.
3. Closed-session minutes (weekends, CFD daily break) are dropped when
   building candles.
"""

from __future__ import annotations

import hashlib
import math
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd

from market_data.models import AssetClass, AssetSpec, SessionType, Timeframe
from market_data.sessions import WEEKLY_CLOSE_HOUR, open_mask

EPOCH = datetime(2022, 1, 3, tzinfo=UTC)  # a Monday
HORIZON_DAYS = 365 * 14
MINUTES_PER_DAY = 1440
_BLOCK_DAYS = 12
_DAY_CACHE_SIZE = 96
_BIN_CACHE_SIZE = 1024

# Regime codes for the daily generator.
_TREND_UP, _TREND_DOWN, _RANGE, _VOLATILE, _QUIET = range(5)


def stable_seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "little")


def _intraday_profile(asset_class: AssetClass) -> np.ndarray:
    """Per-minute volatility weights (UTC), normalised so sum(w**2) == 1."""
    minutes = np.arange(MINUTES_PER_DAY)
    hours = minutes / 60.0
    if asset_class == AssetClass.CRYPTO:
        w = 1.0 + 0.25 * np.exp(-((hours - 14.5) ** 2) / 8.0)
    else:
        w = np.full(MINUTES_PER_DAY, 0.55)
        w += 0.25 * ((hours >= 0) & (hours < 7))  # Asia
        w += 0.75 * np.exp(-((hours - 8.5) ** 2) / 3.0)  # London open
        w += 1.05 * np.exp(-((hours - 14.0) ** 2) / 4.0)  # NY open / overlap
        w -= 0.25 * ((hours >= 20) & (hours < 23))  # late NY / rollover lull
        w = np.clip(w, 0.2, None)
    return w / math.sqrt(float(np.sum(w**2)))


class DemoPriceModel:
    def __init__(self, spec: AssetSpec):
        self.spec = spec
        self.seed = stable_seed("nexus-demo:" + spec.symbol)
        self._log_anchor = math.log(spec.demo_anchor_price)
        self._profile = _intraday_profile(spec.asset_class)
        self._vol_profile = self._profile / self._profile.mean()
        self._log_close, self._sigma = self._generate_daily()
        self._day_cache: OrderedDict[int, dict[str, np.ndarray]] = OrderedDict()
        self._bin_cache: OrderedDict[tuple[int, int], dict[str, np.ndarray]] = OrderedDict()
        self._masks: np.ndarray | None = None
        self._daily_bins: dict[int, dict[str, np.ndarray]] = {}

    # ------------------------------------------------------------------ daily
    def _generate_daily(self) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng([self.seed, 1])
        n = HORIZON_DAYS
        z = rng.standard_normal(n)
        n_blocks = n // _BLOCK_DAYS + 1
        regime = rng.choice(5, size=n_blocks, p=[0.22, 0.22, 0.28, 0.13, 0.15])
        strength = rng.uniform(0.18, 0.5, n_blocks)
        vol_mult = rng.uniform(0.8, 1.2, n_blocks)
        base_sigma = self.spec.demo_daily_vol
        crypto = self.spec.session == SessionType.CRYPTO

        log_close = np.empty(n)
        sigma = np.empty(n)
        x_prev = self._log_anchor
        block_start_level = x_prev
        for k in range(n):
            b = k // _BLOCK_DAYS
            if k % _BLOCK_DAYS == 0:
                block_start_level = x_prev
            r = regime[b]
            vm = vol_mult[b] * (1.75 if r == _VOLATILE else 0.6 if r == _QUIET else 1.0)
            s = base_sigma * vm
            drift = 0.0
            if r == _TREND_UP:
                drift = strength[b] * base_sigma
            elif r == _TREND_DOWN:
                drift = -strength[b] * base_sigma
            pull = (self._log_anchor - x_prev) / 160.0
            if r == _RANGE:
                pull += 0.22 * (block_start_level - x_prev)
            weekday = k % 7
            if not crypto and weekday >= 5:
                # Markets are closed: only a small weekend gap accumulates.
                s *= 0.12
                drift = 0.0
                pull = 0.0
            d = drift + pull + s * z[k]
            x_prev = x_prev + d
            log_close[k] = x_prev
            sigma[k] = s
        return log_close, sigma

    @staticmethod
    def day_index(ts: datetime) -> int:
        return int((ts - EPOCH).total_seconds() // 86_400)

    def _prev_close_log(self, k: int) -> float:
        return self._log_anchor if k <= 0 else float(self._log_close[k - 1])

    # ----------------------------------------------------------------- minute
    def day_minutes(self, k: int) -> dict[str, np.ndarray]:
        """Minute OHLCV arrays for day k (length 1440, includes closed minutes)."""
        if k < 0 or k >= HORIZON_DAYS:
            raise ValueError("Requested time is outside the demo model horizon")
        cached = self._day_cache.get(k)
        if cached is not None:
            self._day_cache.move_to_end(k)
            return cached
        rng = np.random.default_rng([self.seed, 3, k])
        z = rng.standard_normal(MINUTES_PER_DAY)
        wick_z = np.abs(rng.standard_normal((2, MINUTES_PER_DAY)))
        vol_noise = rng.lognormal(0.0, 0.28, MINUTES_PER_DAY)
        s = self._profile
        sig = float(self._sigma[k])
        x0 = self._prev_close_log(k)
        d = float(self._log_close[k]) - x0
        r = sig * s * z
        r += (d - r.sum()) * s**2  # Brownian bridge: day ends exactly at its close
        logp = x0 + np.cumsum(r)
        log_open = np.concatenate(([x0], logp[:-1]))
        o = np.exp(log_open)
        c = np.exp(logp)
        wick_scale = 0.35 * sig * s
        h = np.maximum(o, c) * np.exp(wick_z[0] * wick_scale)
        lo = np.minimum(o, c) * np.exp(-wick_z[1] * wick_scale)
        per_min = self.spec.demo_base_volume / 60.0
        v = per_min * self._vol_profile * (0.55 + 0.9 * np.abs(z)) * vol_noise
        data = {"open": o, "high": h, "low": lo, "close": c, "volume": np.round(v)}
        self._day_cache[k] = data
        if len(self._day_cache) > _DAY_CACHE_SIZE:
            self._day_cache.popitem(last=False)
        return data

    # ---------------------------------------------------------------- pricing
    def last_open_minute(self, ts: datetime) -> datetime:
        """Open time of the latest open-session minute at or before ts."""
        t = ts.astimezone(UTC).replace(second=0, microsecond=0)
        if self.spec.session == SessionType.CRYPTO:
            return t
        wd, hour = t.weekday(), t.hour
        friday_close = None
        if wd == 5:
            friday_close = t - timedelta(days=1)
        elif wd == 6 and hour < WEEKLY_CLOSE_HOUR:
            friday_close = t - timedelta(days=2)
        elif wd == 4 and hour >= WEEKLY_CLOSE_HOUR:
            friday_close = t
        if friday_close is not None:
            return friday_close.replace(hour=WEEKLY_CLOSE_HOUR - 1, minute=59)
        if self.spec.session == SessionType.CFD and wd <= 3 and hour == WEEKLY_CLOSE_HOUR:
            return t.replace(hour=WEEKLY_CLOSE_HOUR - 1, minute=59)
        return t

    def price_at(self, ts: datetime) -> float:
        """Deterministic tradable price at ts (interpolated inside the minute)."""
        ts = ts.astimezone(UTC)
        minute = self.last_open_minute(ts)
        k = self.day_index(minute)
        m = int((minute - (EPOCH + timedelta(days=k))).total_seconds() // 60)
        data = self.day_minutes(k)
        o, c = float(data["open"][m]), float(data["close"][m])
        if minute != ts.replace(second=0, microsecond=0):
            return c  # market closed at ts: last traded price
        frac = (ts.second + ts.microsecond / 1e6) / 60.0
        rng = np.random.default_rng([self.seed, 4, k, m, ts.second])
        jitter = float(rng.standard_normal()) * 0.15 * abs(c - o)
        return o + (c - o) * frac + jitter * math.sin(math.pi * frac)

    def spread_at(self, ts: datetime) -> float:
        hour = ts.astimezone(UTC).hour
        widen = 2.2 if hour in (21, 22) else 1.0
        return self.spec.typical_spread * widen

    # ---------------------------------------------------------------- candles
    def _weekday_masks(self) -> np.ndarray:
        if self._masks is None:
            masks = np.zeros((7, MINUTES_PER_DAY), dtype=bool)
            for wd in range(7):
                idx = pd.date_range(EPOCH + timedelta(days=wd), periods=MINUTES_PER_DAY, freq="1min")
                masks[wd] = open_mask(self.spec.session, idx)
            self._masks = masks
        return self._masks

    def _day_bins(self, k: int, tf_min: int, upto_minute: int | None = None) -> dict[str, np.ndarray]:
        """Aggregate day k into tf_min-minute bins using open-session minutes only.

        Returns arrays: t (bin open, epoch seconds), open, high, low, close,
        volume. Bins without any open minute are omitted. When `upto_minute`
        is given only minutes strictly before it are used (partial day).
        """
        key = (k, tf_min)
        if upto_minute is None and tf_min == MINUTES_PER_DAY and k in self._daily_bins:
            return self._daily_bins[k]
        if upto_minute is None:
            cached = self._bin_cache.get(key)
            if cached is not None:
                self._bin_cache.move_to_end(key)
                return cached
        data = self.day_minutes(k)
        mask = self._weekday_masks()[k % 7].copy()
        if upto_minute is not None:
            mask[upto_minute:] = False
        nb = MINUTES_PER_DAY // tf_min
        m2 = mask.reshape(nb, tf_min)
        valid = m2.any(axis=1)
        rows = np.arange(nb)
        first = m2.argmax(axis=1)
        last = tf_min - 1 - m2[:, ::-1].argmax(axis=1)
        o = data["open"].reshape(nb, tf_min)[rows, first]
        c = data["close"].reshape(nb, tf_min)[rows, last]
        h = np.where(m2, data["high"].reshape(nb, tf_min), -np.inf).max(axis=1)
        lo = np.where(m2, data["low"].reshape(nb, tf_min), np.inf).min(axis=1)
        v = np.where(m2, data["volume"].reshape(nb, tf_min), 0.0).sum(axis=1)
        day_start = int((EPOCH + timedelta(days=k)).timestamp())
        t = day_start + rows * tf_min * 60
        out = {
            "t": t[valid],
            "open": o[valid],
            "high": h[valid],
            "low": lo[valid],
            "close": c[valid],
            "volume": v[valid],
        }
        if upto_minute is None and tf_min == MINUTES_PER_DAY:
            self._daily_bins[k] = out  # tiny; kept for the process lifetime
        elif upto_minute is None:
            self._bin_cache[key] = out
            if len(self._bin_cache) > _BIN_CACHE_SIZE:
                self._bin_cache.popitem(last=False)
        return out

    def candles(
        self,
        timeframe: Timeframe,
        end: datetime,
        limit: int,
        start: datetime | None = None,
        now: datetime | None = None,
    ) -> tuple[pd.DataFrame, bool]:
        """Return (frame, last_bar_complete) for bars whose open time < end.

        If `now` falls inside the requested window, the in-progress bar is
        included, built from minutes completed so far plus the current partial
        minute, so the latest bar tracks the live demo price.
        """
        now = (now or datetime.now(UTC)).astimezone(UTC)
        end = min(end.astimezone(UTC), now)
        tf_min = MINUTES_PER_DAY if timeframe in (Timeframe.D1, Timeframe.W1) else timeframe.minutes
        if start is not None:
            begin = max(start.astimezone(UTC), EPOCH)
        else:
            per_bar_days = timeframe.seconds / 86_400
            factor = 1.0 if self.spec.session == SessionType.CRYPTO else 1.5
            begin = max(
                end - timedelta(days=per_bar_days * (limit + 2) * factor + (3 if factor > 1 else 0)), EPOCH
            )
        if timeframe == Timeframe.W1:
            k_b = self.day_index(begin)
            begin = EPOCH + timedelta(days=k_b - k_b % 7)
        now_minute = now.replace(second=0, microsecond=0)
        today = self.day_index(now)
        k0, k1 = self.day_index(begin), self.day_index(end - timedelta(microseconds=1))
        parts: list[dict[str, np.ndarray]] = []
        for k in range(max(k0, 0), k1 + 1):
            if k == today:
                upto = int((now_minute - (EPOCH + timedelta(days=k))).total_seconds() // 60)
                part = self._day_bins(k, tf_min, upto_minute=upto)
                part = self._merge_partial_minute(part, k, upto, tf_min, now)
            else:
                part = self._day_bins(k, tf_min)
            parts.append(part)
        if not parts:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"]), True
        cols = {
            name: np.concatenate([p[name] for p in parts])
            for name in ("t", "open", "high", "low", "close", "volume")
        }
        t = cols.pop("t")
        sel = (t >= begin.timestamp()) & (t < end.timestamp())
        df = pd.DataFrame(
            {k: v[sel] for k, v in cols.items()}, index=pd.to_datetime(t[sel], unit="s", utc=True)
        )
        if timeframe == Timeframe.W1 and len(df):
            week_key = (df.index - pd.Timestamp(EPOCH)).days // 7
            weekly = df.groupby(week_key).agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            )
            weekly.index = pd.DatetimeIndex([EPOCH + timedelta(days=7 * int(w)) for w in weekly.index])
            df = weekly
        if start is None:
            df = df.iloc[-limit:]
        last_complete = True
        if len(df):
            last_open = df.index[-1].to_pydatetime()
            span = timedelta(days=7) if timeframe == Timeframe.W1 else timedelta(seconds=timeframe.seconds)
            last_complete = last_open + span <= now
        return df, last_complete

    def _merge_partial_minute(
        self, part: dict[str, np.ndarray], k: int, minute: int, tf_min: int, now: datetime
    ) -> dict[str, np.ndarray]:
        """Fold the in-progress minute (open -> current demo price) into the bins."""
        if not self._weekday_masks()[k % 7][minute] or (now.second == 0 and now.microsecond == 0):
            return part
        d = self.day_minutes(k)
        o = float(d["open"][minute])
        p = self.price_at(now)
        frac = (now.second + now.microsecond / 1e6) / 60.0
        vol = round(float(d["volume"][minute]) * frac)
        bin_t = int((EPOCH + timedelta(days=k)).timestamp()) + (minute // tf_min) * tf_min * 60
        part = {name: arr.copy() for name, arr in part.items()}
        if len(part["t"]) and part["t"][-1] == bin_t:
            part["high"][-1] = max(part["high"][-1], o, p)
            part["low"][-1] = min(part["low"][-1], o, p)
            part["close"][-1] = p
            part["volume"][-1] += vol
            return part
        for name, val in (
            ("t", bin_t),
            ("open", o),
            ("high", max(o, p)),
            ("low", min(o, p)),
            ("close", p),
            ("volume", vol),
        ):
            part[name] = np.append(part[name], val)
        return part
