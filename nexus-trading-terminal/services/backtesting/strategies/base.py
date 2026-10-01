"""Strategy plugin interface.

A strategy receives a `BarView` positioned at bar t. The view only exposes
data at or before t (indexing with a positive offset raises), so a strategy
cannot peek at future bars. The same strategy objects run in backtests, in
walk-forward validation and in the live strategy ensemble.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from market_data.models import Timeframe
from quant.features.feature_set import compute_indicator_frame
from quant.mtf.alignment import resample_ohlcv
from quant.regime.detector import classify_frame
from quant.signals.models import Direction
from quant.structure.engine import StructureStates, compute_structure_states


class LookAheadError(RuntimeError):
    pass


class StrategyVote(BaseModel):
    strategy: str
    version: str
    direction: Direction = Direction.NO_TRADE
    strength: float = 0.0
    applicable: bool = True
    entry_type: str = "MARKET"  # MARKET | LIMIT | STOP
    entry_price: float | None = None
    stop: float | None = None
    target: float | None = None
    reasons: list[str] = Field(default_factory=list)


class SeriesData:
    """Precomputed causal data for one series (shared by all strategies)."""

    def __init__(
        self,
        df: pd.DataFrame,
        timeframe: Timeframe,
        volume_available: bool = True,
        higher: Timeframe | None = None,
    ):
        self.df = df
        self.timeframe = timeframe
        self.volume_available = volume_available
        self.frame = compute_indicator_frame(df, timeframe, volume_available)
        self.states: StructureStates = compute_structure_states(df)
        self.regimes = classify_frame(self.frame)
        self.open = df["open"].to_numpy(dtype="float64")
        self.high = df["high"].to_numpy(dtype="float64")
        self.low = df["low"].to_numpy(dtype="float64")
        self.close = df["close"].to_numpy(dtype="float64")
        self.cols = {c: self.frame[c].to_numpy(dtype="float64") for c in self.frame.columns}
        self.regime_codes = self.regimes["regime"].to_numpy()
        self.higher = higher
        self.htf_trend = np.full(len(df), np.nan)
        if higher is not None and len(df) > 0:
            htf = resample_ohlcv(df, higher)
            if len(htf) >= 60:
                hf = compute_indicator_frame(htf, higher, volume_available)
                span = (
                    pd.Timedelta(days=7) if higher == Timeframe.W1 else pd.Timedelta(seconds=higher.seconds)
                )
                htf_close = (htf.index + span).asi8
                bar_close = (df.index + pd.Timedelta(seconds=timeframe.seconds)).asi8
                j = np.searchsorted(htf_close, bar_close, side="right") - 1
                ts = hf["trend_score"].to_numpy()
                self.htf_trend = np.where(j >= 0, ts[np.clip(j, 0, len(ts) - 1)], np.nan)

    def __len__(self) -> int:
        return len(self.df)

    @classmethod
    def from_precomputed(
        cls,
        df: pd.DataFrame,
        timeframe: Timeframe,
        frame: pd.DataFrame,
        states: StructureStates,
        regimes: pd.DataFrame,
        volume_available: bool,
        htf_trend_last: float | None,
    ) -> SeriesData:
        """Reuse an already-computed analysis (live path) instead of recomputing indicators."""
        obj = cls.__new__(cls)
        obj.df, obj.timeframe, obj.volume_available = df, timeframe, volume_available
        obj.frame, obj.states, obj.regimes = frame, states, regimes
        obj.open = df["open"].to_numpy(dtype="float64")
        obj.high = df["high"].to_numpy(dtype="float64")
        obj.low = df["low"].to_numpy(dtype="float64")
        obj.close = df["close"].to_numpy(dtype="float64")
        obj.cols = {c: frame[c].to_numpy(dtype="float64") for c in frame.columns}
        obj.regime_codes = regimes["regime"].to_numpy()
        obj.higher = None
        obj.htf_trend = np.full(len(df), np.nan)
        if htf_trend_last is not None and len(df):
            obj.htf_trend[-1] = htf_trend_last
        return obj


class BarView:
    """Read-only window onto SeriesData at bar t. Offsets are <= 0 only."""

    def __init__(self, data: SeriesData, t: int):
        self._d = data
        self.t = t

    def _idx(self, k: int) -> int:
        if k > 0:
            raise LookAheadError("Strategies may not access future bars")
        i = self.t + k
        if i < 0:
            raise IndexError("Not enough history")
        return i

    def get(self, col: str, k: int = 0) -> float:
        return float(self._d.cols[col][self._idx(k)])

    def ohlc(self, k: int = 0) -> tuple[float, float, float, float]:
        i = self._idx(k)
        d = self._d
        return float(d.open[i]), float(d.high[i]), float(d.low[i]), float(d.close[i])

    def lowest_low(self, n: int) -> float:
        lo = max(0, self.t - n + 1)
        return float(np.min(self._d.low[lo : self.t + 1]))

    def highest_high(self, n: int) -> float:
        lo = max(0, self.t - n + 1)
        return float(np.max(self._d.high[lo : self.t + 1]))

    @property
    def regime(self) -> str:
        return str(self._d.regime_codes[self.t])

    @property
    def structure_trend(self) -> int:
        return int(self._d.states.trend[self.t])

    def structure_event(self, max_age: int) -> tuple[int, int, float] | None:
        """(event_code, bars_ago, broken_level) of the latest BOS/CHoCH within max_age bars."""
        lo = max(0, self.t - max_age)
        ev = self._d.states.event[lo : self.t + 1]
        nz = np.nonzero(ev)[0]
        if not len(nz):
            return None
        j = lo + int(nz[-1])
        code = int(self._d.states.event[j])
        level = self._d.states.last_high[j] if code in (1, 3) else self._d.states.last_low[j]
        return code, self.t - j, float(level)

    @property
    def last_swing_low(self) -> float:
        return float(self._d.states.last_low[self.t])

    @property
    def last_swing_high(self) -> float:
        return float(self._d.states.last_high[self.t])

    @property
    def htf_trend(self) -> float:
        return float(self._d.htf_trend[self.t])

    @property
    def volume_available(self) -> bool:
        return self._d.volume_available

    @property
    def timestamp(self) -> pd.Timestamp:
        return self._d.df.index[self.t]


class Strategy(ABC):
    name: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    description: ClassVar[str] = ""
    regimes: ClassVar[tuple[str, ...]] = ()
    defaults: ClassVar[dict[str, Any]] = {}
    grid: ClassVar[dict[str, list[Any]]] = {}
    min_bars: ClassVar[int] = 210

    def __init__(self, **params: Any):
        unknown = set(params) - set(self.defaults)
        if unknown:
            raise ValueError(f"Unknown parameters for {self.name}: {sorted(unknown)}")
        self.params = {**self.defaults, **params}

    def vote(self, view: BarView) -> StrategyVote:
        base = StrategyVote(strategy=self.name, version=self.version)
        if view.t < self.min_bars:
            base.reasons.append("Warm-up: insufficient history")
            return base
        try:
            vote = self.analyze(view)
        except (IndexError, ValueError) as exc:
            base.reasons.append(f"Not evaluable: {exc}")
            return base
        vote.applicable = not self.regimes or view.regime in self.regimes
        return vote

    @abstractmethod
    def analyze(self, view: BarView) -> StrategyVote: ...

    def _vote(
        self,
        direction: Direction,
        strength: float,
        stop: float | None,
        target: float | None,
        reasons: list[str],
        entry_type: str = "MARKET",
        entry_price: float | None = None,
    ) -> StrategyVote:
        return StrategyVote(
            strategy=self.name,
            version=self.version,
            direction=direction,
            strength=float(np.clip(strength, 0, 1)),
            stop=stop,
            target=target,
            reasons=reasons,
            entry_type=entry_type,
            entry_price=entry_price,
        )

    def _none(self, reason: str = "No setup") -> StrategyVote:
        return StrategyVote(strategy=self.name, version=self.version, reasons=[reason])

    @classmethod
    def param_combinations(cls) -> list[dict[str, Any]]:
        if not cls.grid:
            return [dict(cls.defaults)]
        keys = list(cls.grid)
        return [
            {**cls.defaults, **dict(zip(keys, vals, strict=True))}
            for vals in itertools.product(*(cls.grid[k] for k in keys))
        ]

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "regimes": list(self.regimes),
            "params": self.params,
            "grid": self.grid,
        }


def finite(*vals: float) -> bool:
    return all(v is not None and np.isfinite(v) for v in vals)
