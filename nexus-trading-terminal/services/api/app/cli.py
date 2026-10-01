"""Command line: migrate, seed (DEMO data), serve, openapi export.

python -m app.cli migrate
python -m app.cli seed [--fast]
python -m app.cli serve [--reload]
python -m app.cli openapi <path>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, func, select


def _print(msg: str) -> None:
    print(f"[nexus] {msg}", flush=True)


async def seed(fast: bool = False) -> None:
    from app.core.config import get_settings
    from app.core.container import Container
    from app.models import MarketAsset, MarketCandle, Signal
    from backtesting.engine.engine import BacktestConfig
    from market_data.models import Timeframe

    env = get_settings()
    c = Container(env)
    await c.startup(run_background=False)
    if not c.market.is_demo:
        _print(
            "A live market data provider is active; seed only generates DEMO data, so skipping market seeding."
        )
    started = time.perf_counter()
    async with c.db.session() as s:
        for a in c.catalog.all():
            row = await s.get(MarketAsset, a.symbol)
            if row is None:
                s.add(
                    MarketAsset(
                        symbol=a.symbol,
                        name=a.name,
                        asset_class=a.asset_class.value,
                        session=a.session.value,
                        spec=a.model_dump(mode="json"),
                        enabled=True,
                    )
                )
    _print(f"assets: {len(c.catalog.all())} instruments")

    if c.market.is_demo:
        now = c.market.now()
        n = 0
        async with c.db.session() as s:
            await s.execute(delete(MarketCandle).where(MarketCandle.source == "seed"))
        for a in c.catalog.all():
            series = await c.market.candles(a.symbol, Timeframe.H1, start=now - timedelta(days=60), end=now)
            df = series.closed_bars()
            async with c.db.session() as s:
                for ts, row in df.iterrows():
                    s.add(
                        MarketCandle(
                            symbol=a.symbol,
                            timeframe="1H",
                            ts=ts.to_pydatetime(),
                            open=float(row["open"]),
                            high=float(row["high"]),
                            low=float(row["low"]),
                            close=float(row["close"]),
                            volume=float(row["volume"]),
                            provider="demo",
                            source="seed",
                            is_demo=True,
                            batch="demo-seed",
                        )
                    )
            n += len(df)
        _print(f"historical candles: {n} DEMO 1H bars stored (60 days x {len(c.catalog.all())} instruments)")

        await c.content.refresh_calendar(days_back=3, days_ahead=10)
        await c.content.refresh_news(c.ai_providers(), use_ai=False)
        _print("news + economic calendar: DEMO items generated")

        tf = Timeframe.parse(c.settings.get("markets").default_timeframe)
        symbols = c.settings.get("markets").default_assets[: 3 if fast else None]
        t0 = time.perf_counter()
        await c.memory.ensure_built(symbols, [tf], c.signals.engine())
        stats = await c.memory.stats()
        _print(
            f"historical setup memory: {sum(x['records'] for x in stats['counts'])} DEMO setups ({time.perf_counter() - t0:.0f}s)"
        )

        report = await c.memory.train_model()
        _print(f"ML calibration model: {report.status} ({'; '.join(report.reasons[:2])})")

        made = 0
        for sym in c.settings.get("markets").default_assets:
            try:
                await c.signals.generate(sym, tf, use_ai=False, source="seed", force=True)
                made += 1
            except Exception as exc:  # seed should continue on per-symbol issues
                _print(f"signal {sym}: skipped ({getattr(exc, 'message', type(exc).__name__)})")
        async with c.db.session() as s:
            active = list(
                (
                    await s.execute(
                        select(Signal).where(Signal.status == "ACTIVE").order_by(Signal.score.desc())
                    )
                ).scalars()
            )
            total = await s.scalar(select(func.count()).select_from(Signal))
        _print(f"signals: {made} evaluated, {total} stored, {len(active)} ACTIVE (DEMO)")

        await c.paper.ensure_account()
        if active:
            try:
                await c.paper.execute_signal(active[0])
                _print(
                    f"paper account: executed top DEMO signal {active[0].symbol} {active[0].direction} (SIMULATED)"
                )
            except Exception as exc:
                _print(f"paper account: signal not executed ({getattr(exc, 'message', type(exc).__name__)})")
        await c.paper.snapshot()

        if not fast:
            cfg = BacktestConfig(
                symbol="XAUUSD",
                timeframe="1H",
                strategy="TrendFollowing",
                start=now - timedelta(days=180),
                end=now,
            )
            bt = await c.research.run_backtest(cfg)
            _print(f"sample backtest: {bt['id']} ({bt['metrics']['total_trades']} trades, DEMO data)")
    await c.shutdown()
    _print(
        f"seed complete in {time.perf_counter() - started:.0f}s - all seeded market content is labelled DEMO"
    )


def migrate() -> None:
    from app.core.config import get_settings
    from app.core.container import run_migrations

    url = get_settings().sync_database_url
    run_migrations(url)
    _print(f"database migrated to head ({url.split('://')[0]})")


def serve(reload: bool) -> None:
    import uvicorn

    from app.core.config import get_settings

    env = get_settings()
    if env.api_host not in ("127.0.0.1", "localhost", "::1"):
        _print(
            f"WARNING: binding to {env.api_host}. The API has no authentication; only expose it behind an authenticating proxy."
        )
    uvicorn.run(
        "app.main:app",
        host=env.api_host,
        port=env.api_port,
        reload=reload,
        log_config=None,
        reload_dirs=[str(Path(__file__).resolve().parents[2])] if reload else None,
    )


def export_openapi(path: str) -> None:
    from app.main import create_app

    spec = create_app().openapi()
    Path(path).write_text(json.dumps(spec, indent=2), encoding="utf-8")
    _print(f"OpenAPI written to {path} ({len(spec.get('paths', {}))} paths)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nexus")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    sp = sub.add_parser("seed")
    sp.add_argument("--fast", action="store_true", help="Seed fewer instruments (for tests/CI)")
    sv = sub.add_parser("serve")
    sv.add_argument("--reload", action="store_true")
    op = sub.add_parser("openapi")
    op.add_argument("path")
    args = p.parse_args(argv)
    if args.cmd == "migrate":
        migrate()
    elif args.cmd == "seed":
        asyncio.run(seed(args.fast))
    elif args.cmd == "serve":
        serve(args.reload)
    elif args.cmd == "openapi":
        export_openapi(args.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
