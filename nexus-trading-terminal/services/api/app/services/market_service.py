"""Market analysis service: candles, features, structure, regime, MTF, macro, heatmap, psychology.

Analysis always runs on CLOSED bars (no repainting). Bundles are cached per
(provider, symbol, timeframe, last closed bar) and computed in a worker
thread so the event loop stays responsive.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.core.errors import NexusError
from app.providers.market import MarketDataManager
from market_data.assets import AssetCatalog
from market_data.models import ANALYSIS_TIMEFRAMES, AssetSpec, CandleSeries, Quote, Timeframe
from market_data.normalization.validation import DataQualityReport
from market_data.providers.base import MarketDataError
from quant.mtf.alignment import MTFAnalysis, TimeframeView
from quant.signals.context import AnalysisBundle, analyze_series, mtf_from_bundles
from quant.signals.models import MacroContext

BUNDLE_BARS = 500
HTF_BARS = 320


class MarketService:
    def __init__(self, market: MarketDataManager, catalog: AssetCatalog):
        self.market = market
        self.catalog = catalog
        self._bundles: dict[
            tuple[str, str, str], tuple[str, AnalysisBundle, CandleSeries, DataQualityReport]
        ] = {}
        self._locks: dict[tuple[str, str, str], asyncio.Lock] = {}

    def spec(self, symbol: str) -> AssetSpec:
        try:
            return self.catalog.get(symbol)
        except KeyError as exc:
            raise NexusError("INVALID_SYMBOL", f"Unknown symbol '{symbol}'") from exc

    @property
    def mode(self) -> str:
        return self.market.mode

    def meta(self) -> dict[str, Any]:
        return {"mode": self.market.mode, "provider": self.market.active.name, "is_demo": self.market.is_demo}

    # ------------------------------------------------------------- quotes
    async def quote(self, symbol: str) -> Quote:
        return await self.market.quote(self.spec(symbol).symbol)

    async def quotes(self, symbols: list[str] | None = None) -> list[Quote]:
        syms = symbols or self.catalog.symbols()
        results = await asyncio.gather(*(self.market.quote(s) for s in syms), return_exceptions=True)
        return [r for r in results if isinstance(r, Quote)]

    # ------------------------------------------------------------ bundles
    async def bundle(
        self, symbol: str, timeframe: Timeframe, limit: int = BUNDLE_BARS
    ) -> tuple[AnalysisBundle, CandleSeries, DataQualityReport]:
        spec = self.spec(symbol)
        key = (self.market.active.name, spec.symbol, timeframe.value)
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            series, report = await self.market.validated(spec.symbol, timeframe, limit)
            closed = series.closed_bars()
            if len(closed) == 0:
                raise NexusError("INSUFFICIENT_DATA", f"No closed {timeframe.value} bars for {spec.symbol}")
            stamp = f"{closed.index[-1].isoformat()}|{len(closed)}"
            hit = self._bundles.get(key)
            if hit and hit[0] == stamp:
                return hit[1], series, report
            bundle = await asyncio.to_thread(analyze_series, closed, timeframe, series.volume_available)
            self._bundles[key] = (stamp, bundle, series, report)
            return bundle, series, report

    async def mtf(self, symbol: str, primary: Timeframe | None = None) -> MTFAnalysis:
        tfs = list(ANALYSIS_TIMEFRAMES)
        results = await asyncio.gather(
            *(self.bundle(symbol, tf, HTF_BARS if tf != primary else BUNDLE_BARS) for tf in tfs),
            return_exceptions=True,
        )
        bundles: dict[Timeframe, AnalysisBundle | None] = {}
        notes: dict[Timeframe, str] = {}
        for tf, res in zip(tfs, results, strict=True):
            if isinstance(res, BaseException):
                bundles[tf] = None
                notes[tf] = getattr(res, "message", None) or type(res).__name__
            else:
                bundles[tf] = res[0]
        return mtf_from_bundles(bundles, notes)

    # ----------------------------------------------------------- payloads
    async def candles_payload(self, symbol: str, timeframe: Timeframe, limit: int) -> dict[str, Any]:
        spec = self.spec(symbol)
        series, report = await self.market.validated(spec.symbol, timeframe, limit)
        df = series.df
        bars = [
            [
                int(ts.timestamp()),
                round(float(o), spec.price_precision + 2),
                round(float(h), spec.price_precision + 2),
                round(float(lo), spec.price_precision + 2),
                round(float(c), spec.price_precision + 2),
                float(v),
            ]
            for ts, o, h, lo, c, v in zip(
                df.index, df["open"], df["high"], df["low"], df["close"], df["volume"], strict=True
            )
        ]
        return {
            "symbol": spec.symbol,
            "timeframe": timeframe.value,
            "bars": bars,
            "last_bar_complete": series.last_bar_complete,
            "volume_available": series.volume_available,
            "data_quality": report.model_dump(mode="json"),
            "price_precision": spec.price_precision,
            **self.meta(),
            "provider": series.provider,
            "is_demo": series.is_demo,
        }

    async def overlays(self, symbol: str, timeframe: Timeframe) -> dict[str, Any]:
        bundle, _, _ = await self.bundle(symbol, timeframe)
        f = bundle.frame
        ts = [int(t.timestamp()) for t in f.index]

        def line(col: str) -> list[list[float]]:
            vals = f[col].to_numpy(dtype="float64")
            return [[t, round(float(v), 8)] for t, v in zip(ts, vals, strict=True) if np.isfinite(v)]

        st = bundle.structure()
        events = []
        ev = bundle.states.event
        for i in np.nonzero(ev)[0][-30:]:
            code = int(ev[i])
            from quant.structure.engine import EVENT_NAMES

            typ, direction = EVENT_NAMES[code]
            events.append({"time": ts[i], "type": typ, "direction": direction})
        return {
            "symbol": symbol,
            "timeframe": timeframe.value,
            **self.meta(),
            "lines": {
                c: line(c)
                for c in ("ema20", "ema50", "ema200", "sma20", "bb_upper", "bb_mid", "bb_lower", "vwap")
            },
            "panes": {
                c: line(c)
                for c in (
                    "rsi14",
                    "macd",
                    "macd_signal",
                    "macd_hist",
                    "stoch_k",
                    "stoch_d",
                    "adx",
                    "cci20",
                    "obv",
                    "atr14",
                    "volume_sma20",
                )
            },
            "structure": st.model_dump(mode="json"),
            "events": events,
        }

    async def overview(self, symbols: list[str], timeframe: Timeframe = Timeframe.H1) -> list[dict[str, Any]]:
        async def card(sym: str) -> dict[str, Any]:
            base: dict[str, Any] = {"symbol": sym}
            try:
                q = await self.quote(sym)
                bundle, _, report = await self.bundle(sym, timeframe, 320)
                f = bundle.features()
                reg = bundle.regime()
                closes = bundle.df["close"].iloc[-48:].round(8).tolist()
                spec = self.spec(sym)
                base.update(
                    {
                        "name": spec.name,
                        "asset_class": spec.asset_class.value,
                        "price": q.price,
                        "bid": q.bid,
                        "ask": q.ask,
                        "change_24h": q.change_24h,
                        "change_pct_24h": q.change_pct_24h,
                        "market_open": q.market_open,
                        "trend": f.trend,
                        "trend_score": f.trend_score,
                        "momentum_score": f.momentum_score,
                        "atr_pct": f.atr_pct,
                        "vol_percentile": f.vol_percentile,
                        "regime": reg.regime.value,
                        "regime_clarity": reg.clarity,
                        "sparkline": closes,
                        "timeframe": timeframe.value,
                        "price_precision": spec.price_precision,
                        "data_quality": report.quality_score,
                        "is_demo": q.is_demo,
                        "provider": q.provider,
                        "status": "OK",
                    }
                )
            except (MarketDataError, NexusError) as exc:
                base.update({"status": "ERROR", "error": getattr(exc, "message", str(exc)), **self.meta()})
            return base

        return list(await asyncio.gather(*(card(s) for s in symbols)))

    # -------------------------------------------------------------- macro
    async def daily_changes(self, symbols: list[str]) -> dict[str, float]:
        qs = await self.quotes(symbols)
        return {q.symbol: q.change_pct_24h for q in qs if q.change_pct_24h is not None}

    async def macro_context(self, symbol: str, changes: dict[str, float] | None = None) -> MacroContext:
        changes = changes or await self.daily_changes(self.catalog.symbols())
        spec = self.spec(symbol)
        label = " (demo data)" if self.market.is_demo else ""
        usd_parts = []
        for s, sign in (("EURUSD", -1), ("GBPUSD", -1), ("USDJPY", 1)):
            if s != spec.symbol and s in changes:
                usd_parts.append(sign * changes[s])
        if not usd_parts:
            return MacroContext(available=False)
        usd = float(np.mean(usd_parts))
        vol = spec.demo_daily_vol * 100 if spec.demo_daily_vol else 1.0
        usd_z = math.tanh(usd / 0.4)
        risk_parts = [
            changes[s] / (self.spec(s).demo_daily_vol * 100)
            for s in ("NAS100", "SPX500", "US30", "BTCUSD")
            if s in changes and s != spec.symbol
        ]
        risk_on = math.tanh(float(np.mean(risk_parts)) / 1.0) if risk_parts else 0.0
        if spec.symbol in ("XAUUSD", "EURUSD", "GBPUSD"):
            usd_beta, risk_beta = -1.0, (-0.3 if spec.symbol == "XAUUSD" else 0.1)
        elif spec.symbol == "USDJPY":
            usd_beta, risk_beta = 1.0, 0.3
        elif spec.asset_class.value in ("INDICES", "CRYPTO"):
            usd_beta, risk_beta = -0.3, 0.6
        else:
            usd_beta, risk_beta = -0.4, 0.3
        bias = float(np.clip(0.6 * usd_beta * usd_z + 0.4 * risk_beta * risk_on, -1, 1))
        usd_note = f"USD basket {'strengthening' if usd > 0 else 'weakening'} ({usd:+.2f}% 24h, from EURUSD/GBPUSD/USDJPY){label}"
        risk_note = f"Risk sentiment {'risk-on' if risk_on > 0.15 else 'risk-off' if risk_on < -0.15 else 'mixed'} (equity indices/crypto){label}"
        pro_long: list[str] = []
        pro_short: list[str] = []
        (pro_long if usd_beta * usd > 0 else pro_short).append(usd_note)
        if abs(risk_on) > 0.15 and risk_beta != 0:
            (pro_long if risk_beta * risk_on > 0 else pro_short).append(risk_note)
        _ = vol
        return MacroContext(
            available=True,
            bias=round(bias, 4),
            usd_basket_change_pct=round(usd, 4),
            risk_sentiment=round(risk_on, 4),
            notes_for_long=pro_long,
            notes_for_short=pro_short,
        )

    # ------------------------------------------------------- heatmap/psych
    async def correlations(self, symbols: list[str], days: int = 60) -> dict[str, Any]:
        async def closes(sym: str) -> pd.Series | None:
            try:
                s = await self.market.candles(sym, Timeframe.D1, days + 5)
            except MarketDataError:
                return None
            c = s.closed_bars()["close"]
            c.index = c.index.normalize()
            return np.log(c).diff().rename(sym)

        cols = [c for c in await asyncio.gather(*(closes(s) for s in symbols)) if c is not None]
        if len(cols) < 2:
            return {"symbols": [], "matrix": [], "days": days}
        frame = pd.concat(cols, axis=1, sort=True).dropna(how="all").iloc[-days:]
        corr = frame.corr(min_periods=20).round(3)
        return {
            "symbols": list(corr.columns),
            "matrix": corr.fillna(0.0).values.tolist(),
            "days": days,
            "observations": len(frame),
        }

    async def psychology(self, symbols: list[str]) -> dict[str, Any]:
        cards = await self.overview(symbols, Timeframe.H1)
        ok = [c for c in cards if c.get("status") == "OK"]
        changes = {c["symbol"]: c["change_pct_24h"] or 0.0 for c in ok}
        if not ok:
            raise NexusError("DATA_PROVIDER_UNAVAILABLE", "No market data available")
        breadth_up = sum(1 for v in changes.values() if v > 0) / len(changes)
        above_trend = sum(1 for c in ok if (c.get("trend_score") or 0) > 0) / len(ok)
        vols = [c["vol_percentile"] for c in ok if c.get("vol_percentile") is not None]
        moms = [c["momentum_score"] for c in ok if c.get("momentum_score") is not None]
        macro = await self.macro_context("XAUUSD", changes) if "XAUUSD" in self.catalog else MacroContext()
        abs_moves = np.array([abs(v) for v in changes.values()])
        share_top2 = float(np.sort(abs_moves)[-2:].sum() / abs_moves.sum()) if abs_moves.sum() > 0 else None
        hhi = float(((abs_moves / abs_moves.sum()) ** 2).sum()) if abs_moves.sum() > 0 else None
        corr = await self.correlations(symbols)
        avg_corr = None
        if corr["matrix"]:
            m = np.array(corr["matrix"])
            iu = np.triu_indices(len(m), 1)
            avg_corr = round(float(np.mean(np.abs(m[iu]))), 3)
        risk = macro.risk_sentiment or 0.0
        regime_counts: dict[str, int] = {}
        for c in ok:
            regime_counts[c["regime"]] = regime_counts.get(c["regime"], 0) + 1
        return {
            **self.meta(),
            "disclaimer": (
                "MARKET PSYCHOLOGY is inferred from measurable market variables (returns, volatility, breadth, "
                "correlation, momentum, concentration). It does not measure what people think or feel."
            ),
            "risk_appetite": {
                "score": round(risk, 3),
                "label": "RISK-ON" if risk > 0.15 else "RISK-OFF" if risk < -0.15 else "MIXED",
                "usd_basket_change_pct": macro.usd_basket_change_pct,
                "inputs": "24h moves of NAS100, SPX500, US30, BTCUSD scaled by typical volatility; USD basket from EURUSD/GBPUSD/USDJPY",
            },
            "volatility": {
                "average_percentile": round(float(np.mean(vols)), 1) if vols else None,
                "elevated": [c["symbol"] for c in ok if (c.get("vol_percentile") or 0) >= 85],
            },
            "breadth": {
                "pct_up_24h": round(breadth_up * 100, 1),
                "pct_positive_trend": round(above_trend * 100, 1),
                "instruments": len(ok),
            },
            "momentum": {
                "average_score": round(float(np.mean(moms)), 1) if moms else None,
                "strongest": sorted(
                    (
                        {"symbol": c["symbol"], "score": c["momentum_score"]}
                        for c in ok
                        if c.get("momentum_score") is not None
                    ),
                    key=lambda x: -abs(x["score"]),
                )[:3],
            },
            "concentration": {
                "top2_share_of_moves": round(share_top2, 3) if share_top2 is not None else None,
                "herfindahl": round(hhi, 3) if hhi is not None else None,
            },
            "correlation": {"average_abs_correlation": avg_corr, **corr},
            "regimes": regime_counts,
            "assets": [
                {
                    "symbol": c["symbol"],
                    "change_pct_24h": c["change_pct_24h"],
                    "trend_score": c["trend_score"],
                    "momentum_score": c["momentum_score"],
                    "vol_percentile": c["vol_percentile"],
                    "regime": c["regime"],
                }
                for c in ok
            ],
        }

    async def heatmap(self, symbols: list[str], latest_scores: dict[str, float]) -> list[dict[str, Any]]:
        cards = await self.overview(symbols, Timeframe.H1)
        out = []
        for c in cards:
            if c.get("status") != "OK":
                out.append({"symbol": c["symbol"], "status": "ERROR", "error": c.get("error")})
                continue
            bundle, _, _ = await self.bundle(c["symbol"], Timeframe.H1, 320)
            f = bundle.features()
            out.append(
                {
                    "symbol": c["symbol"],
                    "name": c["name"],
                    "asset_class": c["asset_class"],
                    "price": c["price"],
                    "change_pct_24h": c["change_pct_24h"],
                    "volume_ratio": f.volume_ratio,
                    "volume_available": f.volume_available,
                    "atr_pct": c["atr_pct"],
                    "vol_percentile": c["vol_percentile"],
                    "trend": c["trend"],
                    "trend_score": c["trend_score"],
                    "regime": c["regime"],
                    "signal_score": latest_scores.get(c["symbol"]),
                    "is_demo": c["is_demo"],
                    "status": "OK",
                }
            )
        return out

    def now(self) -> datetime:
        return self.market.now()

    @staticmethod
    def view_rows(mtf: MTFAnalysis) -> list[TimeframeView]:
        return mtf.views
