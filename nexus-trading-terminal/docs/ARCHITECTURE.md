# Architecture

NEXUS is a local, single-user application: one FastAPI process (all Python
packages plus background jobs and a WebSocket) and one Next.js server (UI and a
server-side proxy to the API). SQLite is the default store; Redis is optional.

```
 Browser ──HTTP──► Next.js (apps/web) ──/api/* proxy──► FastAPI (services/api)
    │                                                     │
    └────────── WebSocket /ws (quotes, signals, ...) ─────┘
                                                          │
          ┌──────────────┬──────────────┬─────────────────┼──────────────┬──────────────┐
     market_data       quant            ai              risk     paper_trading     backtesting
   (providers,      (indicators,   (Claude, Gemini,  (veto,       (virtual broker,  (strategies,
    validation,      structure,     rule-based demo,  sizing)      fills, journal    engine, metrics,
    cache)           regime, MTF,   prompts, schemas,              feed, analytics)  walk-forward)
                     scoring,       consensus, critic)
                     signals, ML)
```

## Layer boundaries

| Layer | Package | May depend on | Must not |
| --- | --- | --- | --- |
| DATA | `market_data` | – | know about signals, AI or orders |
| QUANT | `quant` | `market_data` models | call AI, touch the DB, place orders |
| AI | `ai` | structured inputs from the API layer | write to the DB, place orders, bypass risk; its tools are read-only |
| RISK | `risk` | `market_data` specs | be overridden by AI or the UI |
| EXECUTION | `paper_trading` | `risk` decisions via the API services | send real orders (live adapters refuse) |
| RESEARCH | `backtesting` | `quant`, `market_data` | read future bars (guarded) |
| API | `services/api/app` | everything above | return secrets or stack traces |
| UI | `apps/web` | the HTTP API only | hold secrets or compute trading decisions |

The API layer (`app/services/*`) is the only place that persists data; it wires
the pure packages together in `app/core/container.py`.

## Signal pipeline

`SignalService.generate()` (`services/api/app/services/signal_service.py`):

1. **Market data** for the primary timeframe and higher timeframes (`MarketService`).
2. **Validation** (`market_data/normalization/validation.py`): gaps, duplicates,
   OHLC consistency, staleness, quality score. Unusable data → NO_TRADE.
3. **Quant**: indicator frame, versioned feature snapshot, market structure, regime,
   multi-timeframe alignment (`quant.signals.context.analyze_series`).
4. **Signal engine**: both directions scored 0–100, objective entry/stop/targets,
   blocking filters (`quant/signals/engine.py`). Strategy ensemble votes are recorded.
5. **AI review** (optional): Claude and Gemini analyse the same structured input
   independently → consensus → critic. AI can only downgrade to NO_TRADE.
6. **Historical matching**: nearest similar labelled setups (`quant/ml/memory.py`);
   insufficient evidence blocks the signal; small samples are labelled.
7. **Risk engine**: deterministic checks and sizing; a veto is final.
8. **Persist** signal, features, AI analyses, outcome tracker row, journal entry;
   broadcast on the WebSocket; optional automatic paper execution.

Background jobs (`app/services/background.py`) stream quotes, scan new bars (one open
setup per instrument/timeframe at a time), track signal outcomes, evaluate alerts,
warn about events, refresh news/calendar, build setup memory, snapshot the portfolio,
check provider health and apply data retention.

## Data provenance

Every payload that carries prices, events or results includes `is_demo`/`provider`
(and `data_mode` for signals). The UI renders these as badges; backtests and paper
trades are additionally labelled BACKTEST / PAPER, screenshot output IMAGE ANALYSIS.

## Frontend

Next.js App Router. Each route `app/<route>/page.tsx` exports metadata and renders a
client `view.tsx`. Data via SWR (`hooks/use-api.ts`), live quotes and events via a
single shared WebSocket client (`lib/live.ts`) with REST polling fallback. The shell
(`components/layout`) provides the status bar, ticker, navigation, intelligence panel,
mobile bottom navigation, command palette and keyboard shortcuts.
