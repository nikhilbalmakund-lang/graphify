"""Strategy lab, backtests, walk-forward validation, strategy-by-regime stats, CSV import and the market scanner."""

from __future__ import annotations

import asyncio
import io
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import delete, select

from app.core.database import Database, utcnow
from app.core.errors import NexusError
from app.models import Backtest, BacktestTrade, MarketCandle, Strategy, StrategyRegimeStat
from app.services.market_service import MarketService
from app.websocket.manager import ConnectionManager
from backtesting.engine.engine import ENGINE_VERSION, BacktestConfig, Backtester, BacktestResult
from backtesting.strategies.base import SeriesData
from backtesting.strategies.library import REGISTRY, create
from backtesting.validation.walk_forward import WalkForwardConfig, WalkForwardResult, run_walk_forward
from market_data.models import CandleSeries, Timeframe
from market_data.normalization.normalize import parse_timestamps
from market_data.normalization.validation import validate_ohlcv_frame
from quant.signals.context import HIGHER_TIMEFRAMES

MAX_BACKTEST_BARS = 60_000
MAX_IMPORT_ROWS = 250_000


class ResearchService:
    def __init__(self, db: Database, market: MarketService, ws: ConnectionManager):
        self.db = db
        self.market = market
        self.ws = ws
        self._sem = asyncio.Semaphore(2)

    async def sync_strategies(self) -> None:
        async with self.db.session() as s:
            for name, cls in REGISTRY.items():
                row = await s.get(Strategy, name)
                inst = cls()
                if row is None:
                    s.add(
                        Strategy(
                            name=name,
                            version=cls.version,
                            description=cls.description,
                            params=inst.params,
                            regimes=list(cls.regimes),
                            enabled=True,
                            updated_at=utcnow(),
                        )
                    )
                else:
                    row.version, row.description, row.params, row.regimes = (
                        cls.version,
                        cls.description,
                        inst.params,
                        list(cls.regimes),
                    )

    def strategies(self) -> list[dict[str, Any]]:
        return [create(n).describe() for n in REGISTRY]

    # --------------------------------------------------------------- data
    async def _series(
        self, symbol: str, tf: Timeframe, start: datetime | None, end: datetime | None, data_source: str
    ) -> CandleSeries:
        if data_source.startswith("imported:"):
            batch = data_source.split(":", 1)[1]
            async with self.db.session() as s:
                q = (
                    select(MarketCandle)
                    .where(
                        MarketCandle.batch == batch,
                        MarketCandle.symbol == symbol,
                        MarketCandle.timeframe == tf.value,
                    )
                    .order_by(MarketCandle.ts)
                )
                if start:
                    q = q.where(MarketCandle.ts >= start)
                if end:
                    q = q.where(MarketCandle.ts <= end)
                rows = list((await s.execute(q)).scalars())
            if not rows:
                raise NexusError(
                    "INSUFFICIENT_DATA", f"No imported candles for batch {batch} / {symbol} / {tf.value}"
                )
            df = pd.DataFrame(
                {
                    "open": [r.open for r in rows],
                    "high": [r.high for r in rows],
                    "low": [r.low for r in rows],
                    "close": [r.close for r in rows],
                    "volume": [r.volume for r in rows],
                },
                index=pd.DatetimeIndex([r.ts for r in rows]),
            )
            return CandleSeries(
                symbol=symbol,
                timeframe=tf,
                provider=f"csv:{batch}",
                is_demo=False,
                df=df,
                last_bar_complete=True,
                volume_available=bool((df["volume"] > 0).any()),
            )
        now = self.market.now()
        end = min(end or now, now)
        start = start or end - timedelta(days=365)
        bars = (end - start).total_seconds() / tf.seconds
        if bars > MAX_BACKTEST_BARS * 1.6:
            raise NexusError(
                "BACKTEST_ERROR",
                f"Date range is too large for {tf.value} (~{int(bars)} bars); maximum is {MAX_BACKTEST_BARS}",
            )
        series = await self.market.market.candles(symbol, tf, limit=MAX_BACKTEST_BARS, start=start, end=end)
        return series

    # ----------------------------------------------------------- backtest
    async def run_backtest(self, cfg: BacktestConfig, data_source: str = "provider") -> dict[str, Any]:
        if cfg.strategy not in REGISTRY:
            raise NexusError("BACKTEST_ERROR", f"Unknown strategy {cfg.strategy}")
        tf = Timeframe.parse(cfg.timeframe)
        spec = self.market.spec(cfg.symbol)
        try:
            strategy = create(cfg.strategy, **cfg.params)
        except ValueError as exc:
            raise NexusError("BACKTEST_ERROR", str(exc)) from exc
        bt_id = f"bt_{uuid.uuid4().hex[:16]}"
        started = time.perf_counter()
        async with self._sem:
            series = await self._series(spec.symbol, tf, cfg.start, cfg.end, data_source)
            df = series.closed_bars()
            if len(df) < strategy.min_bars + 50:
                raise NexusError(
                    "INSUFFICIENT_DATA", f"Need at least {strategy.min_bars + 50} bars; got {len(df)}"
                )
            higher = HIGHER_TIMEFRAMES[tf][0] if HIGHER_TIMEFRAMES[tf] else None

            def work() -> BacktestResult:
                data = SeriesData(df, tf, series.volume_available, higher=higher)
                return Backtester(data, spec, cfg, provider=series.provider, is_demo=series.is_demo).run(
                    strategy
                )

            try:
                result = await asyncio.to_thread(work)
            except Exception as exc:
                await self._save_failed(bt_id, "BACKTEST", cfg, series, str(exc))
                raise NexusError("BACKTEST_ERROR", f"Backtest failed: {type(exc).__name__}") from exc
        payload = result.model_dump(mode="json")
        payload.pop("trades", None)
        await self._save(
            bt_id,
            "BACKTEST",
            cfg,
            strategy.version,
            series,
            result.metrics.metrics.model_dump(),
            payload,
            result.warnings,
            result.trades,
            started,
        )
        await self._regime_stats(cfg.strategy, result.metrics.by_regime, series.is_demo)
        await self.ws.broadcast("backtests", {"event": "COMPLETED", "id": bt_id, "strategy": cfg.strategy})
        return await self.get(bt_id)

    async def run_walk_forward(self, wf: WalkForwardConfig, data_source: str = "provider") -> dict[str, Any]:
        cfg = wf.backtest
        if cfg.strategy not in REGISTRY:
            raise NexusError("BACKTEST_ERROR", f"Unknown strategy {cfg.strategy}")
        tf = Timeframe.parse(cfg.timeframe)
        spec = self.market.spec(cfg.symbol)
        bt_id = f"wf_{uuid.uuid4().hex[:16]}"
        started = time.perf_counter()
        async with self._sem:
            series = await self._series(spec.symbol, tf, cfg.start, cfg.end, data_source)
            df = series.closed_bars()
            higher = HIGHER_TIMEFRAMES[tf][0] if HIGHER_TIMEFRAMES[tf] else None

            def work() -> WalkForwardResult:
                data = SeriesData(df, tf, series.volume_available, higher=higher)
                return run_walk_forward(data, spec, wf, provider=series.provider, is_demo=series.is_demo)

            try:
                result = await asyncio.to_thread(work)
            except ValueError as exc:
                raise NexusError("INSUFFICIENT_DATA", str(exc)) from exc
            except Exception as exc:
                await self._save_failed(bt_id, "WALK_FORWARD", cfg, series, str(exc))
                raise NexusError("BACKTEST_ERROR", f"Walk-forward failed: {type(exc).__name__}") from exc
        payload = result.model_dump(mode="json")
        payload.pop("oos_trades", None)
        payload["walk_forward_config"] = wf.model_dump(mode="json", exclude={"backtest"})
        await self._save(
            bt_id,
            "WALK_FORWARD",
            cfg,
            create(cfg.strategy).version,
            series,
            result.oos_metrics.metrics.model_dump(),
            payload,
            result.warnings,
            result.oos_trades,
            started,
        )
        return await self.get(bt_id)

    async def _save(
        self,
        bt_id: str,
        kind: str,
        cfg: BacktestConfig,
        version: str,
        series: CandleSeries,
        metrics: dict[str, Any],
        result: dict[str, Any],
        warnings: list[str],
        trades: list[Any],
        started: float,
    ) -> None:
        async with self.db.session() as s:
            s.add(
                Backtest(
                    id=bt_id,
                    kind=kind,
                    strategy=cfg.strategy,
                    strategy_version=version,
                    symbol=cfg.symbol,
                    timeframe=cfg.timeframe,
                    params=cfg.params,
                    config=cfg.model_dump(mode="json"),
                    status="COMPLETED",
                    metrics=metrics,
                    result=result,
                    is_demo=series.is_demo,
                    provider=series.provider,
                    data_label=(
                        "DEMO BACKTEST (synthetic data)"
                        if series.is_demo
                        else f"BACKTEST ({series.provider})"
                    ),
                    warnings=warnings,
                    engine_version=ENGINE_VERSION,
                    created_at=utcnow(),
                    completed_at=utcnow(),
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )
            )
            await s.flush()
            for t in trades:
                s.add(
                    BacktestTrade(
                        backtest_id=bt_id,
                        trade_no=t.trade_no,
                        direction=t.direction,
                        entry_time=t.entry_time,
                        exit_time=t.exit_time,
                        entry_price=t.entry_price,
                        exit_price=t.exit_price,
                        lots=t.lots,
                        pnl=t.pnl,
                        pnl_r=t.pnl_r,
                        fees=t.fees,
                        exit_reason=t.exit_reason,
                        regime=t.regime,
                        bars_held=t.bars_held,
                        mfe_r=t.mfe_r,
                        mae_r=t.mae_r,
                    )
                )

    async def _save_failed(
        self, bt_id: str, kind: str, cfg: BacktestConfig, series: CandleSeries, error: str
    ) -> None:
        async with self.db.session() as s:
            s.add(
                Backtest(
                    id=bt_id,
                    kind=kind,
                    strategy=cfg.strategy,
                    strategy_version="n/a",
                    symbol=cfg.symbol,
                    timeframe=cfg.timeframe,
                    params=cfg.params,
                    config=cfg.model_dump(mode="json"),
                    status="FAILED",
                    is_demo=series.is_demo,
                    provider=series.provider,
                    data_label="FAILED",
                    warnings=[],
                    error=error[:2000],
                    engine_version=ENGINE_VERSION,
                    created_at=utcnow(),
                )
            )

    async def _regime_stats(self, strategy: str, by_regime: list[Any], is_demo: bool) -> None:
        """Latest backtest per strategy defines its BACKTEST regime statistics (replaced, not accumulated)."""
        async with self.db.session() as s:
            await s.execute(
                delete(StrategyRegimeStat).where(
                    StrategyRegimeStat.strategy == strategy,
                    StrategyRegimeStat.source == "BACKTEST",
                    StrategyRegimeStat.is_demo == is_demo,
                )
            )
            for r in by_regime:
                wins = round((r.win_rate or 0) * r.trades)
                s.add(
                    StrategyRegimeStat(
                        strategy=strategy,
                        regime=r.regime,
                        source="BACKTEST",
                        is_demo=is_demo,
                        trades=r.trades,
                        wins=wins,
                        sum_r=(r.average_r or 0.0) * r.trades,
                        sum_pnl=r.net_profit,
                        updated_at=utcnow(),
                    )
                )

    async def list_backtests(self, limit: int = 50) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = list(
                (
                    await s.execute(select(Backtest).order_by(Backtest.created_at.desc()).limit(limit))
                ).scalars()
            )
        return [self._summary(r) for r in rows]

    @staticmethod
    def _summary(r: Backtest) -> dict[str, Any]:
        return {
            "id": r.id,
            "kind": r.kind,
            "strategy": r.strategy,
            "strategy_version": r.strategy_version,
            "symbol": r.symbol,
            "timeframe": r.timeframe,
            "params": r.params,
            "status": r.status,
            "metrics": r.metrics,
            "is_demo": r.is_demo,
            "provider": r.provider,
            "data_label": r.data_label,
            "warnings": r.warnings,
            "error": r.error,
            "created_at": r.created_at.isoformat(),
            "duration_ms": r.duration_ms,
            "engine_version": r.engine_version,
        }

    async def get(self, bt_id: str) -> dict[str, Any]:
        async with self.db.session() as s:
            r = await s.get(Backtest, bt_id)
            if r is None:
                raise NexusError("NOT_FOUND", f"Backtest {bt_id} not found")
            trades = list(
                (
                    await s.execute(
                        select(BacktestTrade)
                        .where(BacktestTrade.backtest_id == bt_id)
                        .order_by(BacktestTrade.trade_no)
                    )
                ).scalars()
            )
        d = self._summary(r)
        d["config"] = r.config
        d["result"] = r.result
        d["trades"] = [
            {
                "trade_no": t.trade_no,
                "direction": t.direction,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "lots": t.lots,
                "pnl": t.pnl,
                "pnl_r": t.pnl_r,
                "fees": t.fees,
                "exit_reason": t.exit_reason,
                "regime": t.regime,
                "bars_held": t.bars_held,
                "mfe_r": t.mfe_r,
                "mae_r": t.mae_r,
            }
            for t in trades
        ]
        return d

    async def regime_performance(self) -> list[dict[str, Any]]:
        async with self.db.session() as s:
            rows = list((await s.execute(select(StrategyRegimeStat))).scalars())
        return [
            {
                "strategy": r.strategy,
                "regime": r.regime,
                "source": r.source,
                "is_demo": r.is_demo,
                "trades": r.trades,
                "win_rate": round(r.wins / r.trades, 4) if r.trades else None,
                "average_r": round(r.sum_r / r.trades, 3) if r.trades else None,
                "net_pnl": round(r.sum_pnl, 2),
                "sample_note": "small sample" if r.trades < 30 else "",
            }
            for r in rows
        ]

    # ------------------------------------------------------------- import
    async def import_csv(
        self, content: bytes, symbol: str, timeframe: Timeframe, filename: str
    ) -> dict[str, Any]:
        spec = self.market.spec(symbol)
        try:
            raw = pd.read_csv(io.BytesIO(content))
        except Exception as exc:
            raise NexusError("INVALID_MARKET_DATA", f"Could not parse CSV: {type(exc).__name__}") from exc
        raw.columns = [str(c).strip().lower() for c in raw.columns]
        ts_col = next((c for c in ("timestamp", "time", "datetime", "date") if c in raw.columns), None)
        if ts_col is None:
            raise NexusError(
                "INVALID_MARKET_DATA", "CSV needs a timestamp column (timestamp/time/datetime/date)"
            )
        if len(raw) > MAX_IMPORT_ROWS:
            raise NexusError(
                "INVALID_MARKET_DATA", f"Too many rows ({len(raw)}); maximum is {MAX_IMPORT_ROWS}"
            )
        missing = [c for c in ("open", "high", "low", "close", "volume") if c not in raw.columns]
        if missing:
            raise NexusError("INVALID_MARKET_DATA", f"Missing columns: {missing}")
        idx = parse_timestamps(raw[ts_col])
        df = pd.DataFrame(
            {
                c: pd.to_numeric(raw[c], errors="coerce").to_numpy()
                for c in ("open", "high", "low", "close", "volume")
            },
            index=idx,
        )
        errors = validate_ohlcv_frame(df)
        if errors:
            raise NexusError(
                "INVALID_MARKET_DATA", "CSV rejected: " + "; ".join(errors[:6]), {"errors": errors}
            )
        if (df.index > pd.Timestamp(datetime.now(UTC) + timedelta(minutes=5))).any():
            raise NexusError("INVALID_MARKET_DATA", "CSV rejected: timestamps in the future")
        batch = f"{spec.symbol.lower()}_{timeframe.value}_{uuid.uuid4().hex[:8]}"
        async with self.db.session() as s:
            for ts, row in df.iterrows():
                s.add(
                    MarketCandle(
                        symbol=spec.symbol,
                        timeframe=timeframe.value,
                        ts=ts.to_pydatetime(),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        provider=f"csv:{batch}",
                        source="import",
                        is_demo=False,
                        batch=batch,
                        created_at=utcnow(),
                    )
                )
        return {
            "batch": batch,
            "symbol": spec.symbol,
            "timeframe": timeframe.value,
            "rows": len(df),
            "filename": filename[:200],
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
            "data_source": f"imported:{batch}",
        }

    async def imports(self) -> list[dict[str, Any]]:
        from sqlalchemy import func

        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(
                        MarketCandle.batch,
                        MarketCandle.symbol,
                        MarketCandle.timeframe,
                        func.count(),
                        func.min(MarketCandle.ts),
                        func.max(MarketCandle.ts),
                    )
                    .where(MarketCandle.source == "import")
                    .group_by(MarketCandle.batch, MarketCandle.symbol, MarketCandle.timeframe)
                )
            ).all()
        return [
            {
                "batch": b,
                "symbol": sym,
                "timeframe": tf,
                "rows": n,
                "start": a.isoformat(),
                "end": z.isoformat(),
                "data_source": f"imported:{b}",
            }
            for b, sym, tf, n, a, z in rows
        ]


class ScannerService:
    """Quant-only opportunity scan (no AI calls, for cost control)."""

    def __init__(self, signals: Any, market: MarketService, content: Any, settings: Any):
        self.signals = signals
        self.market = market
        self.content = content
        self.settings = settings
        self._cache: tuple[float, str, list[dict[str, Any]]] | None = None

    async def scan(self, timeframe: Timeframe, symbols: list[str]) -> list[dict[str, Any]]:
        key = f"{timeframe.value}|{','.join(symbols)}"
        if self._cache and self._cache[1] == key and time.monotonic() - self._cache[0] < 30:
            return self._cache[2]
        rows: list[dict[str, Any]] = []
        for sym in symbols:
            try:
                sig = await self.signals.generate(sym, timeframe, use_ai=False, source="scanner")
            except NexusError as exc:
                rows.append({"symbol": sym, "status": "ERROR", "error": exc.message})
                continue
            q = await self.market.quote(sym)
            ev = await self.content.event_risk(sym)
            features = (sig.get("analysis") or {}).get("features") or {}
            news_risk = bool(
                ev.available
                and ev.next_high_impact_minutes is not None
                and ev.next_high_impact_minutes <= 120
            )
            vp = features.get("vol_percentile")
            rows.append(
                {
                    "symbol": sym,
                    "status": "OK",
                    "signal_id": sig["id"],
                    "price": q.price,
                    "change_pct_24h": q.change_pct_24h,
                    "trend": "BULLISH"
                    if (features.get("trend_score") or 0) >= 20
                    else "BEARISH"
                    if (features.get("trend_score") or 0) <= -20
                    else "NEUTRAL",
                    "trend_score": features.get("trend_score"),
                    "regime": sig["regime"],
                    "score": sig["score"],
                    "direction": sig["direction"],
                    "proposed_direction": sig["proposed_direction"],
                    "signal_status": sig["status"],
                    "rr": sig["effective_rr"],
                    "vol_percentile": vp,
                    "news_risk": news_risk,
                    "next_event": ev.next_high_impact_event,
                    "next_event_minutes": ev.next_high_impact_minutes,
                    "risk": "HIGH"
                    if news_risk or (vp or 0) >= 90
                    else "ELEVATED"
                    if (vp or 0) >= 75
                    else "NORMAL",
                    "no_trade_reasons": sig["no_trade_reasons"][:3],
                    "is_demo": sig["is_demo"],
                }
            )
        self._cache = (time.monotonic(), key, rows)
        return rows
