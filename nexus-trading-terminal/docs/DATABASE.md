# Database

SQLAlchemy 2 (async) models in `services/api/app/models/tables.py`; Alembic
migrations in `database/migrations` (config `database/alembic.ini`). The API
applies migrations automatically at startup; `npm run db:migrate` does it
manually. Default store: SQLite at `data/nexus.db` (WAL mode, foreign keys on).
All timestamps are timezone-aware UTC.

## Tables

| Table | Purpose |
| --- | --- |
| `market_assets` | Instrument catalogue (specs: precision, pip size, contract size, sessions) |
| `market_candles` | Stored OHLCV bars (seeded DEMO history and imported CSV batches), with `source`, `batch`, `is_demo` |
| `market_features` | Versioned feature snapshots |
| `market_regimes` | Regime classifications with evidence and version |
| `signals` | Every signal (incl. NO_TRADE): direction, score, components, filters, plan, evidence, AI summary, risk decision, versions, data mode |
| `signal_features` | Full analysis snapshot behind a signal (features, structure, MTF, regime, data quality, context) |
| `signal_ai_analysis` | Each AI output (Claude, Gemini, consensus, critic) with prompt name/version/date, model, settings, validation, tokens, cost, latency |
| `signal_outcomes` | Outcome tracking (filled, exit, R multiple, MFE/MAE, targets hit) |
| `historical_setups` | Labelled setup memory used for similarity evidence and calibration |
| `news` | Normalised news with source attribution, sentiment and source of sentiment |
| `economic_events` | Calendar events (previous / forecast / actual, impact) |
| `paper_accounts`, `paper_positions`, `paper_orders`, `paper_fills` | Virtual broker state (cascade on account reset) |
| `portfolio_snapshots` | Periodic equity / balance / drawdown snapshots |
| `trade_journal` | Signals, paper trades and manual trades with AI reasoning, notes and tags |
| `strategies` | Strategy registry with versions |
| `strategy_regime_stats` | Strategy performance by regime (from backtests) |
| `backtests`, `backtest_trades` | Backtest / walk-forward runs, configuration, metrics, curves and trades |
| `model_versions` | Trained model reports (e.g. calibration model) |
| `ai_calls` | Every AI request: provider, model, purpose, tokens, cost estimate, latency, status, cache hits |
| `briefings` | AI / rule-based market briefings by session |
| `system_events` | Audit log (signals, AI calls, orders, risk events, settings changes, errors) |
| `app_settings` | Validated settings by category |
| `alerts`, `notifications` | Alert rules and the notification feed |

## Indexes

Composite indexes cover the hot paths: candles, features and regimes by
`(symbol, timeframe, ts)`; signals by `(symbol, created_at)`, `status` and
`(symbol, timeframe, bar_time)` (one evaluation per bar); setups by
`(symbol, timeframe, direction, is_demo)`; positions and orders by
`(account_id, status)`; snapshots by `(account_id, ts)`; journal by
`(symbol, entry_time)`.

## Versioning

Rows record the versions that produced them: `feature_version`,
`signal_engine` / `risk_engine` / strategy versions, regime version, prompt
`name@version` and model names, backtest `engine_version`.

## Migrations

```bash
cd services
.venv/bin/alembic -c ../database/alembic.ini revision --autogenerate -m "describe change"
.venv/bin/alembic -c ../database/alembic.ini upgrade head
.venv/bin/alembic -c ../database/alembic.ini check      # model vs. migration drift
```

SQLite migrations use batch mode (`render_as_batch=True`).

## Retention

`DATA_RETENTION_DAYS` (or Settings → Data retention) lets a background job delete
resolved records older than the limit; NO_TRADE signals can have a shorter limit.
Empty means keep everything. Back up by copying `data/nexus.db` while the API is stopped.
