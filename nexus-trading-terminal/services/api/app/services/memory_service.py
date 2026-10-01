"""Historical setup memory backed by the historical_setups table, plus the calibrated ML model."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from app.core.database import Database, utcnow
from app.models import HistoricalSetup, ModelVersion
from app.providers.market import MarketDataManager
from market_data.models import Timeframe
from quant.ml.calibration import MODEL_NAME, MODEL_VERSION, CalibrationReport, SetupProbabilityModel
from quant.ml.memory import (
    ConditionsSummary,
    SetupOutcome,
    SetupRecord,
    build_setup_memory,
    evidence_from,
    find_similar,
    summarize_conditions,
)
from quant.signals.engine import SignalEngine
from quant.signals.models import HistoricalEvidence

logger = logging.getLogger("nexus.memory")
BUILD_DAYS = {"1m": 5, "5m": 25, "15m": 90, "30m": 150, "1H": 365, "4H": 900, "1D": 1400}


def _record(row: HistoricalSetup) -> SetupRecord:
    return SetupRecord(
        symbol=row.symbol,
        timeframe=row.timeframe,
        timestamp=row.ts.isoformat(),
        direction=row.direction,
        score=row.score,
        regime=row.regime,
        asset_class=row.asset_class,
        vector=row.vector,
        entry_type=row.entry_type,
        entry=row.entry,
        stop=row.stop,
        effective_rr=row.effective_rr,
        outcome=SetupOutcome(
            status=row.outcome_status,
            r_multiple=row.r_multiple,
            exit_reason=row.exit_reason,
            bars_held=row.bars_held,
            mfe_r=row.mfe_r or 0.0,
            mae_r=row.mae_r or 0.0,
            tp1_before_sl=row.tp1_before_sl,
        ),
        is_demo=row.is_demo,
        provider=row.provider,
        source=row.source,
        feature_version=row.feature_version,
        signal_engine_version=row.signal_engine_version,
    )


class MemoryService:
    def __init__(self, db: Database, market: MarketDataManager):
        self.db = db
        self.market = market
        self._cache: dict[tuple[str, str, bool], list[SetupRecord]] = {}
        self.status: dict[str, Any] = {"state": "IDLE", "built": [], "pending": [], "errors": []}
        self.model = SetupProbabilityModel()
        self._lock = asyncio.Lock()

    async def count(self, symbol: str, timeframe: str, is_demo: bool) -> int:
        async with self.db.session() as s:
            return int(
                await s.scalar(
                    select(func.count())
                    .select_from(HistoricalSetup)
                    .where(
                        HistoricalSetup.symbol == symbol,
                        HistoricalSetup.timeframe == timeframe,
                        HistoricalSetup.is_demo == is_demo,
                    )
                )
                or 0
            )

    async def build(
        self, symbol: str, timeframe: Timeframe, engine: SignalEngine, force: bool = False
    ) -> int:
        is_demo = self.market.is_demo
        if not force and await self.count(symbol, timeframe.value, is_demo):
            return 0
        now = self.market.now()
        series = await self.market.candles(
            symbol, timeframe, start=now - timedelta(days=BUILD_DAYS[timeframe.value]), end=now
        )
        df = series.closed_bars()
        spec = self.market.catalog.get(symbol)
        records = await asyncio.to_thread(
            build_setup_memory,
            df,
            timeframe,
            spec,
            provider=series.provider,
            is_demo=series.is_demo,
            engine=engine,
            step=3,
            volume_available=series.volume_available,
        )
        await self.store(records, replace=(symbol, timeframe.value, series.is_demo, "HISTORICAL_BUILD"))
        return len(records)

    async def store(
        self,
        records: list[SetupRecord],
        replace: tuple[str, str, bool, str] | None = None,
        signal_id: str | None = None,
    ) -> None:
        async with self.db.session() as s:
            if replace:
                sym, tf, demo, source = replace
                await s.execute(
                    delete(HistoricalSetup).where(
                        HistoricalSetup.symbol == sym,
                        HistoricalSetup.timeframe == tf,
                        HistoricalSetup.is_demo == demo,
                        HistoricalSetup.source == source,
                    )
                )
            for r in records:
                s.add(
                    HistoricalSetup(
                        symbol=r.symbol,
                        timeframe=r.timeframe,
                        ts=datetime.fromisoformat(r.timestamp),
                        direction=r.direction,
                        score=r.score,
                        regime=r.regime,
                        asset_class=r.asset_class,
                        vector=r.vector,
                        entry_type=r.entry_type,
                        entry=r.entry,
                        stop=r.stop,
                        effective_rr=r.effective_rr,
                        outcome_status=r.outcome.status,
                        r_multiple=r.outcome.r_multiple,
                        exit_reason=r.outcome.exit_reason,
                        bars_held=r.outcome.bars_held,
                        mfe_r=r.outcome.mfe_r,
                        mae_r=r.outcome.mae_r,
                        tp1_before_sl=r.outcome.tp1_before_sl,
                        is_demo=r.is_demo,
                        provider=r.provider,
                        source=r.source,
                        feature_version=r.feature_version,
                        signal_engine_version=r.signal_engine_version,
                        signal_id=signal_id,
                        created_at=utcnow(),
                    )
                )
        for r in records:
            self._cache.pop((r.symbol, r.timeframe, r.is_demo), None)

    async def ensure_built(
        self, symbols: list[str], timeframes: list[Timeframe], engine: SignalEngine
    ) -> None:
        async with self._lock:
            jobs = [(s, tf) for tf in timeframes for s in symbols]
            self.status = {
                "state": "BUILDING",
                "built": [],
                "pending": [f"{s}:{tf.value}" for s, tf in jobs],
                "errors": [],
                "started_at": utcnow().isoformat(),
            }
            for sym, tf in jobs:
                key = f"{sym}:{tf.value}"
                try:
                    n = await self.build(sym, tf, engine)
                    self.status["built"].append({"key": key, "records": n})
                except Exception as exc:  # one asset failing must not stop the others
                    self.status["errors"].append(
                        {"key": key, "error": getattr(exc, "message", type(exc).__name__)}
                    )
                    logger.warning(
                        "memory_build_failed", extra={"event": "memory_build_failed", "data": {"key": key}}
                    )
                finally:
                    self.status["pending"] = [p for p in self.status["pending"] if p != key]
            self.status["state"] = "READY"
            self.status["finished_at"] = utcnow().isoformat()

    async def candidates(self, symbol: str, timeframe: str, is_demo: bool) -> list[SetupRecord]:
        key = (symbol, timeframe, is_demo)
        if key not in self._cache:
            async with self.db.session() as s:
                rows = (
                    await s.execute(
                        select(HistoricalSetup).where(
                            HistoricalSetup.symbol == symbol,
                            HistoricalSetup.timeframe == timeframe,
                            HistoricalSetup.is_demo == is_demo,
                        )
                    )
                ).scalars()
                self._cache[key] = [_record(r) for r in rows]
        return self._cache[key]

    async def lookup(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        vector: list[float] | None,
        regime: str,
        is_demo: bool,
        k: int = 50,
    ) -> HistoricalEvidence | None:
        if vector is None:
            return None
        pool = [r for r in await self.candidates(symbol, timeframe, is_demo) if r.direction == direction]
        if not pool and self.status.get("state") == "BUILDING":
            return None
        return evidence_from(find_similar(vector, regime, pool, k=k), is_demo)

    async def conditions(
        self, symbol: str, timeframe: str, vector: list[float], regime: str, is_demo: bool, k: int = 50
    ) -> tuple[ConditionsSummary, list[dict[str, Any]]]:
        pool = await self.candidates(symbol, timeframe, is_demo)
        matches = find_similar(vector, regime, pool, k=k)
        rows = [
            {
                "timestamp": m.record.timestamp,
                "direction": m.record.direction,
                "regime": m.record.regime,
                "score": m.record.score,
                "outcome": m.record.outcome.status,
                "r_multiple": m.record.outcome.r_multiple,
                "distance": m.distance,
            }
            for m in matches
        ]
        return summarize_conditions(matches, is_demo), rows

    async def stats(self) -> dict[str, Any]:
        async with self.db.session() as s:
            rows = (
                await s.execute(
                    select(
                        HistoricalSetup.symbol,
                        HistoricalSetup.timeframe,
                        HistoricalSetup.is_demo,
                        func.count(),
                    ).group_by(HistoricalSetup.symbol, HistoricalSetup.timeframe, HistoricalSetup.is_demo)
                )
            ).all()
        return {
            "status": self.status,
            "counts": [{"symbol": a, "timeframe": b, "is_demo": c, "records": d} for a, b, c, d in rows],
        }

    # ----------------------------------------------------------------- ML
    async def train_model(self) -> CalibrationReport:
        is_demo = self.market.is_demo
        async with self.db.session() as s:
            rows = (
                await s.execute(select(HistoricalSetup).where(HistoricalSetup.is_demo == is_demo))
            ).scalars()
            records = [_record(r) for r in rows]
        report = await asyncio.to_thread(self.model.fit, records, "DEMO" if is_demo else "LIVE")
        async with self.db.session() as s:
            version = f"{MODEL_VERSION}+{report.trained_at[:19]}"
            s.add(
                ModelVersion(
                    kind="ML",
                    provider="scikit-learn",
                    model=MODEL_NAME,
                    version=version,
                    config={"features": "similarity vector + direction + score + R:R + regime + asset class"},
                    report=report.model_dump(mode="json"),
                    first_used_at=utcnow(),
                    last_used_at=utcnow(),
                    uses=0,
                )
            )
        return report

    async def restore_model(self) -> str | None:
        """Refit the probability model after a restart if the last stored report passed validation.

        Only the report is persisted (no pickled models); refitting on the same stored
        history is deterministic and re-runs the same out-of-sample gate.
        """
        last = await self.latest_report()
        if not last or last.get("status") != "CALIBRATED":
            return None
        report = await self.train_model()
        return report.status

    async def latest_report(self) -> dict[str, Any] | None:
        if self.model.report is not None:
            return self.model.report.model_dump(mode="json")
        async with self.db.session() as s:
            row = await s.scalar(
                select(ModelVersion)
                .where(ModelVersion.kind == "ML")
                .order_by(ModelVersion.id.desc())
                .limit(1)
            )
            return row.report if row else None

    def probability(
        self,
        vector: list[float] | None,
        direction: str,
        score: float,
        rr: float,
        regime: str,
        asset_class: str,
        is_demo: bool,
    ) -> float | None:
        rep = self.model.report
        if vector is None or rep is None or rep.data_mode != ("DEMO" if is_demo else "LIVE"):
            return None
        return self.model.predict(vector, direction, score, rr, regime, asset_class)
