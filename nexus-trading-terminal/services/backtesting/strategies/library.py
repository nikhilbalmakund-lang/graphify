"""Initial deterministic strategy library.

Each strategy is symmetric (LONG/SHORT), defines its stop from price
structure or volatility and a target from an explicit rule. None of these
are presented as profitable; their performance must be measured.
"""

from __future__ import annotations

from backtesting.strategies.base import BarView, Strategy, StrategyVote, finite
from quant.signals.models import Direction

TRENDING = ("TRENDING_BULLISH", "TRENDING_BEARISH", "BREAKOUT")


class TrendFollowing(Strategy):
    name = "TrendFollowing"
    description = "EMA20/EMA50 trend with ADX filter; enters on a pull-back to EMA20 that closes back in trend direction."
    regimes = TRENDING
    defaults = {"adx_min": 20.0, "pullback_atr": 0.6, "rr": 2.0}
    grid = {"adx_min": [18.0, 22.0, 26.0], "rr": [1.5, 2.0, 2.5]}

    def analyze(self, v: BarView) -> StrategyVote:
        e20, e50, adx, atr, slope = (v.get(c) for c in ("ema20", "ema50", "adx", "atr14", "ema50_slope_atr"))
        o, h, lo, c = v.ohlc()
        if not finite(e20, e50, adx, atr, slope) or atr <= 0 or adx < self.params["adx_min"]:
            return self._none("Trend filter not met")
        pb = self.params["pullback_atr"] * atr
        if e20 > e50 and slope > 0 and lo <= e20 + pb and c > e20 and c > o:
            stop = v.lowest_low(6) - 0.2 * atr
            risk = c - stop
            if risk <= 0:
                return self._none()
            return self._vote(Direction.LONG, min(1.0, adx / 40), stop, c + self.params["rr"] * risk,
                              [f"EMA20 > EMA50, ADX {adx:.0f}, pull-back to EMA20 held"])
        if e20 < e50 and slope < 0 and h >= e20 - pb and c < e20 and c < o:
            stop = v.highest_high(6) + 0.2 * atr
            risk = stop - c
            if risk <= 0:
                return self._none()
            return self._vote(Direction.SHORT, min(1.0, adx / 40), stop, c - self.params["rr"] * risk,
                              [f"EMA20 < EMA50, ADX {adx:.0f}, pull-back to EMA20 rejected"])
        return self._none("No pull-back entry")


class VWAPMomentum(Strategy):
    name = "VWAPMomentum"
    description = "VWAP reclaim/loss with rising MACD histogram, RSI in a momentum band and above-average volume."
    regimes = ("TRENDING_BULLISH", "TRENDING_BEARISH", "BREAKOUT", "UNCERTAIN", "HIGH_VOLATILITY")
    defaults = {"vol_ratio_min": 1.1, "rsi_lo": 52.0, "rsi_hi": 72.0, "rr": 2.0}
    grid = {"vol_ratio_min": [1.0, 1.2, 1.4], "rr": [1.5, 2.0, 2.5]}

    def analyze(self, v: BarView) -> StrategyVote:
        if not v.volume_available:
            return self._none("Requires volume/VWAP")
        vw, vw1, c1 = v.get("vwap"), v.get("vwap", -1), v.get("close", -1)
        hist, hist1, rsi, vr, atr = v.get("macd_hist"), v.get("macd_hist", -1), v.get("rsi14"), v.get("volume_ratio"), v.get("atr14")
        _, _, _, c = v.ohlc()
        if not finite(vw, vw1, c1, hist, hist1, rsi, vr, atr) or atr <= 0 or vr < self.params["vol_ratio_min"]:
            return self._none("Momentum/volume filter not met")
        lo_b, hi_b = self.params["rsi_lo"], self.params["rsi_hi"]
        if c1 < vw1 and c > vw and hist > 0 and hist > hist1 and lo_b <= rsi <= hi_b:
            stop = min(v.lowest_low(3), vw - 0.5 * atr) - 0.1 * atr
            risk = c - stop
            return self._vote(Direction.LONG, min(1.0, vr / 2), stop, c + self.params["rr"] * risk,
                              [f"VWAP reclaim, volume {vr:.1f}x, RSI {rsi:.0f}"]) if risk > 0 else self._none()
        if c1 > vw1 and c < vw and hist < 0 and hist < hist1 and (100 - hi_b) <= rsi <= (100 - lo_b):
            stop = max(v.highest_high(3), vw + 0.5 * atr) + 0.1 * atr
            risk = stop - c
            return self._vote(Direction.SHORT, min(1.0, vr / 2), stop, c - self.params["rr"] * risk,
                              [f"VWAP loss, volume {vr:.1f}x, RSI {rsi:.0f}"]) if risk > 0 else self._none()
        return self._none("No VWAP cross with momentum")


class Breakout(Strategy):
    name = "Breakout"
    description = "Close beyond the prior 20-bar range after a volatility squeeze; measured-move target."
    regimes = ("BREAKOUT", "LOW_VOLATILITY", "RANGING", "UNCERTAIN")
    defaults = {"squeeze_pct": 40.0, "vol_ratio_min": 1.2, "min_rr": 1.5}
    grid = {"squeeze_pct": [30.0, 40.0, 55.0], "min_rr": [1.5, 2.0]}

    def analyze(self, v: BarView) -> StrategyVote:
        ph, pl, atr, bbw1 = v.get("prior_high20"), v.get("prior_low20"), v.get("atr14"), v.get("bb_width_percentile", -1)
        _, _, lo, c = v.ohlc()
        _, h, _, _ = v.ohlc()
        if not finite(ph, pl, atr, bbw1) or atr <= 0 or bbw1 > self.params["squeeze_pct"]:
            return self._none("No squeeze before breakout")
        if v.volume_available:
            vr = v.get("volume_ratio")
            if not finite(vr) or vr < self.params["vol_ratio_min"]:
                return self._none("Breakout without volume expansion")
        height = ph - pl
        if c > ph + 0.1 * atr:
            stop = min(lo - 0.25 * atr, c - 0.5 * atr)
            risk = c - stop
            target = max(ph + height, c + self.params["min_rr"] * risk)
            return self._vote(Direction.LONG, 0.7, stop, target, [f"Breakout above {ph:.5g} after squeeze"])
        if c < pl - 0.1 * atr:
            stop = max(h + 0.25 * atr, c + 0.5 * atr)
            risk = stop - c
            target = min(pl - height, c - self.params["min_rr"] * risk)
            return self._vote(Direction.SHORT, 0.7, stop, target, [f"Breakdown below {pl:.5g} after squeeze"])
        return self._none("Price inside range")


class MeanReversion(Strategy):
    name = "MeanReversion"
    description = "In low-ADX ranges, fade a Bollinger Band excursion once price closes back inside; target the mid-band."
    regimes = ("RANGING", "MEAN_REVERSION", "LOW_VOLATILITY")
    defaults = {"rsi_low": 30.0, "rsi_high": 70.0, "adx_max": 20.0}
    grid = {"rsi_low": [25.0, 30.0, 35.0], "adx_max": [18.0, 22.0]}

    def analyze(self, v: BarView) -> StrategyVote:
        adx, atr, mid = v.get("adx"), v.get("atr14"), v.get("bb_mid")
        lower, lower1, upper, upper1 = v.get("bb_lower"), v.get("bb_lower", -1), v.get("bb_upper"), v.get("bb_upper", -1)
        rsi1, c1 = v.get("rsi14", -1), v.get("close", -1)
        _, _, _, c = v.ohlc()
        if not finite(adx, atr, mid, lower, lower1, upper, upper1, rsi1, c1) or atr <= 0 or adx > self.params["adx_max"]:
            return self._none("Not a low-ADX range")
        if c1 < lower1 and c > lower and rsi1 < self.params["rsi_low"]:
            stop = v.lowest_low(3) - 0.3 * atr
            risk, reward = c - stop, mid - c
            if risk > 0 and reward >= risk:
                return self._vote(Direction.LONG, 0.6, stop, mid, ["Lower-band excursion reversed inside the band"])
        if c1 > upper1 and c < upper and rsi1 > self.params["rsi_high"]:
            stop = v.highest_high(3) + 0.3 * atr
            risk, reward = stop - c, c - mid
            if risk > 0 and reward >= risk:
                return self._vote(Direction.SHORT, 0.6, stop, mid, ["Upper-band excursion reversed inside the band"])
        return self._none("No band re-entry")


class MarketStructure(Strategy):
    name = "MarketStructure"
    description = "After a BOS/CHoCH, enter on a retest of the broken level that holds; stop beyond the last swing."
    regimes = ("TRENDING_BULLISH", "TRENDING_BEARISH", "BREAKOUT", "UNCERTAIN")
    defaults = {"max_event_age": 10, "retest_atr": 0.3, "rr": 2.0}
    grid = {"max_event_age": [6, 10, 15], "rr": [1.5, 2.0, 2.5]}

    def analyze(self, v: BarView) -> StrategyVote:
        ev = v.structure_event(int(self.params["max_event_age"]))
        atr = v.get("atr14")
        if ev is None or not finite(atr) or atr <= 0:
            return self._none("No recent structure break")
        code, age, level = ev
        if age < 1 or not finite(level):
            return self._none("Break too recent for a retest")
        _, h, lo, c = v.ohlc()
        tol = self.params["retest_atr"] * atr
        if code in (1, 3) and v.structure_trend == 1 and lo <= level + tol and c > level:
            stop = min(v.last_swing_low, lo) - 0.25 * atr if finite(v.last_swing_low) else lo - 0.5 * atr
            risk = c - stop
            if 0 < risk <= 4 * atr:
                return self._vote(Direction.LONG, 0.75 if code == 1 else 0.65, stop, c + self.params["rr"] * risk,
                                  [f"{'BOS' if code == 1 else 'CHoCH'} up {age} bars ago; retest of {level:.5g} held"])
        if code in (2, 4) and v.structure_trend == -1 and h >= level - tol and c < level:
            stop = max(v.last_swing_high, h) + 0.25 * atr if finite(v.last_swing_high) else h + 0.5 * atr
            risk = stop - c
            if 0 < risk <= 4 * atr:
                return self._vote(Direction.SHORT, 0.75 if code == 2 else 0.65, stop, c - self.params["rr"] * risk,
                                  [f"{'BOS' if code == 2 else 'CHoCH'} down {age} bars ago; retest of {level:.5g} rejected"])
        return self._none("No retest")


class MultiTimeframeConfluence(Strategy):
    name = "MultiTimeframeConfluence"
    description = "Higher-timeframe and primary trend agree; enter when primary momentum turns in the trend direction."
    regimes = ("TRENDING_BULLISH", "TRENDING_BEARISH", "BREAKOUT")
    defaults = {"trend_min": 25.0, "rr": 2.0}
    grid = {"trend_min": [20.0, 30.0, 40.0], "rr": [1.5, 2.0, 2.5]}

    def analyze(self, v: BarView) -> StrategyVote:
        htf, ts, m, m1, atr = v.htf_trend, v.get("trend_score"), v.get("momentum_score"), v.get("momentum_score", -1), v.get("atr14")
        _, _, _, c = v.ohlc()
        if not finite(htf, ts, m, m1, atr) or atr <= 0:
            return self._none("Higher-timeframe data unavailable")
        tm = self.params["trend_min"]
        if htf >= tm and ts >= tm and m1 <= 0 < m:
            stop = v.lowest_low(10) - 0.2 * atr
            risk = c - stop
            if risk > 0:
                return self._vote(Direction.LONG, min(1.0, (htf + ts) / 160), stop, c + self.params["rr"] * risk,
                                  [f"HTF trend {htf:.0f}, primary {ts:.0f}, momentum turned up"])
        if htf <= -tm and ts <= -tm and m1 >= 0 > m:
            stop = v.highest_high(10) + 0.2 * atr
            risk = stop - c
            if risk > 0:
                return self._vote(Direction.SHORT, min(1.0, -(htf + ts) / 160), stop, c - self.params["rr"] * risk,
                                  [f"HTF trend {htf:.0f}, primary {ts:.0f}, momentum turned down"])
        return self._none("No confluence trigger")


REGISTRY: dict[str, type[Strategy]] = {
    cls.name: cls for cls in (TrendFollowing, VWAPMomentum, Breakout, MeanReversion, MarketStructure, MultiTimeframeConfluence)
}


def create(name: str, **params) -> Strategy:
    try:
        cls = REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown strategy '{name}'. Available: {sorted(REGISTRY)}") from exc
    return cls(**params)
