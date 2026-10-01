"""Build analysis bundles and signal contexts from OHLCV data.

The same functions serve live analysis (t = last bar), the historical setup
memory and backtests (any t, using only bars <= t).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from market_data.models import AssetSpec, Timeframe
from market_data.normalization.validation import DataQualityReport
from quant.features.feature_set import FeatureSnapshot, compute_indicator_frame, snapshot_at
from quant.mtf.alignment import MTFAnalysis, TimeframeView, build_view, closed_htf_bars, combine, resample_ohlcv
from quant.regime.detector import RegimeResult, classify_frame, detect_regime
from quant.signals.models import EventRisk, MacroContext, SentimentContext, SignalContext
from quant.structure.engine import StructureSnapshot, StructureStates, analyze_structure, compute_structure_states


@dataclass
class AnalysisBundle:
    timeframe: Timeframe
    df: pd.DataFrame
    frame: pd.DataFrame
    states: StructureStates
    regimes: pd.DataFrame
    volume_available: bool

    def features(self, t: int = -1) -> FeatureSnapshot:
        return snapshot_at(self.frame, t, self.volume_available)

    def structure(self, t: int | None = None) -> StructureSnapshot:
        return analyze_structure(self.df, self.frame, intraday=self.timeframe.is_intraday, states=self.states, t=t)

    def regime(self, t: int = -1) -> RegimeResult:
        return detect_regime(self.frame, t, classified=self.regimes)

    def view(self) -> TimeframeView:
        st = self.structure()
        return build_view(self.timeframe, self.frame, structure_trend=st.trend, regime=self.regime().regime.value,
                          supports=[lv.price for lv in st.supports], resistances=[lv.price for lv in st.resistances])


def analyze_series(df: pd.DataFrame, timeframe: Timeframe, volume_available: bool = True,
                   swing_left: int = 3, swing_right: int = 3) -> AnalysisBundle:
    frame = compute_indicator_frame(df, timeframe, volume_available)
    states = compute_structure_states(df, swing_left, swing_right)
    regimes = classify_frame(frame)
    return AnalysisBundle(timeframe=timeframe, df=df, frame=frame, states=states, regimes=regimes,
                          volume_available=volume_available)


def mtf_from_bundles(bundles: dict[Timeframe, AnalysisBundle | None], notes: dict[Timeframe, str] | None = None) -> MTFAnalysis:
    views = []
    for tf, b in bundles.items():
        if b is None or len(b.df) < 60:
            views.append(TimeframeView(timeframe=tf.value, available=False, note=(notes or {}).get(tf, "Insufficient data")))
        else:
            views.append(b.view())
    return combine(views)


def mtf_from_resample(df: pd.DataFrame, base: Timeframe, t: int, higher: list[Timeframe],
                      volume_available: bool = True) -> MTFAnalysis:
    """MTF built only from higher-timeframe bars already closed at bar t (for backtests/memory)."""
    views: list[TimeframeView] = []
    for tf in higher:
        htf = closed_htf_bars(df, base, tf, t)
        if len(htf) < 60:
            views.append(TimeframeView(timeframe=tf.value, available=False, note="Insufficient closed higher-timeframe bars"))
            continue
        frame = compute_indicator_frame(htf, tf, volume_available)
        states = compute_structure_states(htf)
        trend_code = {1: "BULLISH", -1: "BEARISH"}.get(int(states.trend[-1]), "NEUTRAL")
        views.append(build_view(tf, frame, structure_trend=trend_code))
    return combine(views)


def build_context(*, symbol: str, spec: AssetSpec, bundle: AnalysisBundle, t: int, mtf: MTFAnalysis,
                  data_quality: DataQualityReport, bid: float | None = None, ask: float | None = None,
                  market_open: bool = True, is_demo: bool = True, provider: str = "demo",
                  spread_is_estimate: bool = False, macro: MacroContext | None = None,
                  sentiment: SentimentContext | None = None, events: EventRisk | None = None,
                  ensemble: dict | None = None) -> SignalContext:
    features = bundle.features(t)
    price = features.close
    half = spec.typical_spread / 2.0
    pos = t if t >= 0 else len(bundle.df) + t
    return SignalContext(
        symbol=symbol, timeframe=bundle.timeframe.value, timestamp=bundle.df.index[pos].isoformat(), price=price,
        bid=bid if bid is not None else price - half, ask=ask if ask is not None else price + half,
        spread_is_estimate=spread_is_estimate, is_demo=is_demo, provider=provider, market_open=market_open,
        features=features, structure=bundle.structure(pos), regime=bundle.regime(pos), mtf=mtf,
        data_quality=data_quality, macro=macro or MacroContext(), sentiment=sentiment or SentimentContext(),
        events=events or EventRisk(), ensemble=ensemble, price_precision=spec.price_precision,
    )


class PrecomputedMTF:
    """Higher-timeframe views for any base bar t using only HTF bars closed by then.

    HTF indicator frames and structure states are computed once (they are
    causal), so historical contexts are cheap to build.
    """

    def __init__(self, df: pd.DataFrame, base: Timeframe, higher: list[Timeframe], volume_available: bool = True):
        self.base = base
        self.items: list[tuple[Timeframe, pd.DataFrame | None, StructureStates | None, np.ndarray | None]] = []
        bar_close = (df.index + pd.Timedelta(seconds=base.seconds)).asi8
        for tf in higher:
            htf = resample_ohlcv(df, tf)
            if len(htf) < 60:
                self.items.append((tf, None, None, None))
                continue
            frame = compute_indicator_frame(htf, tf, volume_available)
            states = compute_structure_states(htf)
            span = pd.Timedelta(days=7) if tf == Timeframe.W1 else pd.Timedelta(seconds=tf.seconds)
            j = np.searchsorted((htf.index + span).asi8, bar_close, side="right") - 1
            self.items.append((tf, frame, states, j))

    def at(self, t: int) -> MTFAnalysis:
        views: list[TimeframeView] = []
        for tf, frame, states, jarr in self.items:
            j = int(jarr[t]) if jarr is not None else -1
            if frame is None or states is None or j < 59:
                views.append(TimeframeView(timeframe=tf.value, available=False, note="Insufficient closed higher-timeframe bars"))
                continue
            trend_code = {1: "BULLISH", -1: "BEARISH"}.get(int(states.trend[j]), "NEUTRAL")
            views.append(build_view(tf, frame.iloc[j: j + 1], structure_trend=trend_code))
        return combine(views)


HIGHER_TIMEFRAMES: dict[Timeframe, list[Timeframe]] = {
    Timeframe.M1: [Timeframe.M5, Timeframe.M15, Timeframe.H1],
    Timeframe.M5: [Timeframe.M15, Timeframe.H1, Timeframe.H4],
    Timeframe.M15: [Timeframe.H1, Timeframe.H4],
    Timeframe.M30: [Timeframe.H1, Timeframe.H4],
    Timeframe.H1: [Timeframe.H4, Timeframe.D1],
    Timeframe.H4: [Timeframe.D1],
    Timeframe.D1: [Timeframe.W1],
    Timeframe.W1: [],
}
