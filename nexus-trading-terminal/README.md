# NEXUS Trading Intelligence

A single-user, local AI trading research terminal. NEXUS combines a deterministic
quantitative pipeline (indicators, market structure, regimes, multi-timeframe
alignment, a 0–100 signal score and hard filters) with independent reviews from
Claude and Gemini, an AI critic, historical setup matching, a deterministic risk
engine with final veto, a realistic backtester, and a paper-trading broker.

It is a research and decision-support tool. It does not give financial advice,
does not promise returns and does not trade real money: live execution is
disabled by default and no live broker adapter ships with this build.

> **Data honesty.** NEXUS never invents market data, news, economic events, AI
> results or backtest performance. Without provider keys it runs in **DEMO MODE**
> on deterministic simulated data, and every screen labels each value as
> **LIVE**, **DEMO**, **IMPORTED**, **BACKTEST**, **PAPER** or **IMAGE ANALYSIS**.
> Signal scores are shown as `SIGNAL SCORE 78/100`, never as a win probability;
> a probability is shown only when an out-of-sample-calibrated model supports it.

---

## Contents

1. [What it does](#what-it-does)
2. [Architecture](#architecture)
3. [Requirements](#requirements)
4. [Installation](#installation)
5. [Environment variables](#environment-variables)
6. [Demo mode](#demo-mode)
7. [Running locally](#running-locally)
8. [Running tests](#running-tests)
9. [Backtesting](#backtesting)
10. [Paper trading](#paper-trading)
11. [External integrations](#external-integrations)
12. [Security](#security)
13. [Deployment](#deployment)
14. [Troubleshooting](#troubleshooting)

---

## What it does

| Area | Pages | Highlights |
| --- | --- | --- |
| Overview | Dashboard, Markets, Chart | Market cards (price, change, trend, volatility, regime), live ticker, multi-timeframe matrix, professional chart (candles, volume, 13 indicators, panes, S/R, BOS/CHoCH, liquidity*, entry/stop/targets, drawings, fullscreen) |
| Intelligence | AI Signals, Market Scanner, AI Chart Scanner, AI Analyst, Research | Signal cards with score breakdown, filters, AI consensus/critic, historical evidence and risk decision; scanner with filters; screenshot analysis labelled IMAGE ANALYSIS; tool-using analyst chat; research reports with bullish/bearish/no-trade scenarios |
| Context | Economic Calendar, News, Heatmap, Market Psychology | High-impact countdowns, source-attributed news (never fabricated URLs), sentiment, heatmap by asset class, risk-on/off, breadth, concentration and correlation |
| Research | Strategy Lab, Backtesting, Analytics | Six versioned strategies, regime performance, calibration model, setup memory, "last N similar conditions", backtests and walk-forward with overfitting checks, P&L/expectancy/R analytics, AI model analytics |
| Trading | Paper Trading, Portfolio, Trade Journal, Alerts | Simulated market/limit/stop orders, kill switch, exposure and equity, automatic journal with notes/tags, configurable alerts |
| System | System Status, Settings | Honest connection states, audit log, background jobs; providers, write-only API keys, risk, signals, AI, appearance, notifications, retention, JSON config export/import |

Keyboard: `/` or `Ctrl+K` search & commands · `G` dashboard · `M` markets ·
`S` signals · `C` chart · `A` AI analyst · `B` backtesting · `P` paper trading · `?` help.

## Architecture

```
Market data ─► Validation ─► Quant (indicators, structure, regime, MTF) ─► Signal engine (score + filters)
   ─► Claude ┐
   ─► Gemini ┴─► Consensus ─► AI critic ─► Historical matching ─► RISK ENGINE (veto) ─► Final signal
   ─► Paper trade ─► Journal ─► Setup memory
```

* **Layers are separate:** DATA (`services/market_data`), QUANT (`services/quant`),
  AI (`services/ai`), RISK (`services/risk`), EXECUTION (`services/paper_trading`),
  RESEARCH (`services/backtesting`), API (`services/api`), UI (`apps/web`).
* **AI is advisory only.** It receives structured inputs, returns schema-validated JSON,
  can only downgrade a setup to NO_TRADE, uses read-only tools, cannot write to the
  database, cannot place orders and cannot bypass the risk engine.
* **One backend process** (FastAPI) hosts all Python packages plus background jobs
  (quotes, scanning, signal tracking, alerts, briefings, retention) and a WebSocket.
* **The browser only talks to Next.js**, which proxies `/api/*` to FastAPI server-side;
  live updates use the API WebSocket with automatic REST fallback.

```
nexus-trading-terminal/
├── apps/web/                 Next.js 16 + React 19 + TypeScript + Tailwind 4 terminal UI
├── packages/shared-types/    API types shared with the UI
├── services/
│   ├── api/app/              FastAPI app: routes, services, models, websocket, CLI, tests
│   ├── market_data/          providers (demo, Twelve Data), sessions, validation, cache
│   ├── quant/                indicators, features, structure, regime, MTF, scoring, signals, ML gate
│   ├── ai/                   providers (Claude, Gemini, rule-based demo), prompts, schemas, consensus, critic
│   ├── risk/                 deterministic risk engine and position sizing
│   ├── backtesting/          strategies, event-driven engine, metrics, walk-forward, overfitting checks
│   └── paper_trading/        paper broker, fills, portfolio analytics, live-broker stubs
├── database/                 Alembic config and migrations
├── docs/                     architecture and subsystem documentation
├── scripts/                  setup / dev / start / python launcher (cross-platform)
└── docker-compose.yml
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/QUANT_ENGINE.md](docs/QUANT_ENGINE.md) ·
[docs/AI_SYSTEM.md](docs/AI_SYSTEM.md) · [docs/RISK_ENGINE.md](docs/RISK_ENGINE.md) ·
[docs/BACKTESTING.md](docs/BACKTESTING.md) · [docs/DATABASE.md](docs/DATABASE.md) ·
[docs/API.md](docs/API.md) · [docs/TESTING.md](docs/TESTING.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

## Requirements

* **Node.js ≥ 20.9** and npm ≥ 10
* **Python 3.11+**
* Optional: Docker with Compose v2.24+ (for `docker compose up`)
* Optional: Redis (an in-process cache is used otherwise)

## Installation

### Option A — local (recommended for development)

```bash
cd nexus-trading-terminal
npm run setup     # venv + backend deps, npm install, .env from .env.example, migrations
npm run demo      # seed DEMO data (~1–2 min), then start API + web
```

Open **http://localhost:3000**. Afterwards `npm run dev` is enough.

Manual equivalent:

```bash
python3 -m venv services/.venv
services/.venv/bin/pip install -r services/api/requirements-dev.txt
npm install
cp .env.example .env
npm run db:migrate
npm run seed
npm run dev
```

Running the API without npm: `cd services && PYTHONPATH=.:api .venv/bin/python -m app.cli serve`
(Windows: `set PYTHONPATH=.;api` and `.venv\Scripts\python`).

### Option B — Docker

```bash
cd nexus-trading-terminal
cp .env.example .env              # optional; DEMO mode works without it
docker compose up --build         # web on http://localhost:3000, API on http://localhost:8000
docker compose run --rm api python -m app.cli seed      # optional: richer DEMO history
```

## Environment variables

All variables are optional; see [.env.example](.env.example) for the complete,
commented list. The most important:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | – | Enables Claude (analyst, critic, explanations, chat, briefings, chart scanner) |
| `GEMINI_API_KEY` | – | Enables Gemini (independent analyst, chart scanner) |
| `CLAUDE_MODEL_FAST` / `CLAUDE_MODEL_STRONG` | `claude-haiku-4-5` / `claude-opus-5-5` | Claude model routing |
| `GEMINI_MODEL_FAST` / `GEMINI_MODEL_STRONG` | `gemini-3.8-flash` / `gemini-3.1-pro-preview` | Gemini model routing |
| `MARKET_DATA_PROVIDER`, `MARKET_DATA_API_KEY` | `demo` | `twelvedata` for live prices |
| `NEWS_PROVIDER`, `NEWS_API_KEY` | `demo` | `finnhub` for real headlines |
| `ECONOMIC_CALENDAR_PROVIDER`, `ECONOMIC_CALENDAR_API_KEY` | `demo` | `fmp` for a real calendar |
| `BROKER`, `BROKER_API_KEY`, `BROKER_API_SECRET` | `paper` | Only the paper broker is implemented |
| `LIVE_TRADING_ENABLED` | `false` | Server-side gate for real orders; keep `false` |
| `DATABASE_URL` | SQLite `data/nexus.db` | Database location |
| `REDIS_URL` | – | Optional shared cache |
| `DEFAULT_MARKET`, `DEFAULT_TIMEFRAME` | `XAUUSD`, `15m` | Initial defaults |
| `RISK_PER_TRADE`, `MAX_DAILY_LOSS` | `0.01`, `0.03` | Initial risk limits (fractions of equity) |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Allowed browser origins |

Keys can also be entered in **Settings → Data & API keys**; they are stored in the
git-ignored `.secrets.env` (owner-only permissions) and never returned to the browser.

## Demo mode

With no keys, NEXUS runs end-to-end on deterministic simulated data:

* **Prices/candles:** a seeded regime-switching model generates the same history every
  run (UTC trading sessions approximated per asset class).
* **News/calendar:** synthetic items, prefixed `[DEMO]`, with no URLs.
* **AI:** a rule-based fallback produces clearly labelled *non-AI* summaries; image
  analysis and AI signal review are unavailable rather than faked.
* **Seed (`npm run seed`)** stores DEMO candles, news, events, labelled historical
  setups (so evidence filters and calibration can work), sample signals, a paper
  position and a sample backtest — all flagged `is_demo`.

The top bar, a persistent banner and per-value badges show **DEMO MODE** whenever
simulated data is in use. Results derived from DEMO data describe synthetic prices only.

## Running locally

| Command | What it does |
| --- | --- |
| `npm run dev` | API with auto-reload on :8000 + Next.js dev server on :3000 |
| `npm run demo` | `seed` then `dev` |
| `npm run seed` | Deterministic DEMO seed (`npm run seed -- --fast` for a quicker, smaller seed) |
| `npm run db:migrate` | Apply Alembic migrations (also run automatically at API start) |
| `npm run build` / `npm start` | Production build of the web app / run API + `next start` |
| `npm run gen:types` | Export OpenAPI JSON and generate `packages/shared-types/src/api.d.ts` |

API docs: http://127.0.0.1:8000/docs (Swagger) and `/redoc`.

## Running tests

```bash
npm test             # backend pytest (≈160 tests) + web unit tests (vitest)
npm run lint         # ruff (lint + format check) + ESLint
npm run typecheck    # mypy + tsc
npm run build && npm run test:e2e   # Playwright end-to-end (desktop + mobile), isolated DEMO database
npm run security     # bandit, pip-audit, npm audit (production deps)
```

See [docs/TESTING.md](docs/TESTING.md).

## Backtesting

**Backtesting** page (or `POST /api/backtests`): choose strategy, asset, timeframe,
date range, capital, risk per trade, spread, commission, slippage, sizing, partial exits.

* Event-driven, bar-by-bar; strategies only see closed bars through a guarded view
  (look-ahead raises an error). Orders fill at the **next bar's open** (gaps honoured),
  with spread, slippage and commission; if stop and target fall inside one bar the
  **stop is assumed first** (pessimistic).
* Reports every required metric — trades, win rate, profit factor, expectancy, average R,
  max drawdown, Sharpe, Sortino, CAGR, volatility, exposure, largest win/loss, longest
  losing streak — plus equity, drawdown, monthly returns, R distribution, results by
  regime, the full trade list (CSV export) and **every losing period**.
* **Walk-forward** mode chooses parameters on TRAIN, confirms on VALIDATION, reports on
  unseen TEST windows and rolls forward, with overfitting flags.
* Historical OHLCV CSVs can be imported (Markets page) and selected as the data source.

## Paper trading

The **Paper Trading** page is a virtual broker labelled *SIMULATED* everywhere:
market, limit and stop orders; stop loss required by default; up to three take-profits;
spread/slippage-aware fills; partial closes; breakeven management; an **emergency kill
switch** that cancels pending orders and blocks new ones. Every order — manual or from a
signal — passes the deterministic risk engine first. Fills, positions and P&L feed the
Portfolio page and the Trade Journal automatically. Paper mode never sends a real order.

## External integrations

| Integration | Enable with | Notes |
| --- | --- | --- |
| Claude (Anthropic) | `ANTHROPIC_API_KEY` | Structured JSON outputs, adaptive effort, manual read-only tool loop |
| Gemini (Google) | `GEMINI_API_KEY` | JSON-schema outputs, function declarations with manual execution |
| Twelve Data | `MARKET_DATA_PROVIDER=twelvedata`, `MARKET_DATA_API_KEY` | Live quotes and candles; free plans may not cover every symbol (use `MARKET_DATA_SYMBOL_MAP`) |
| Finnhub | `NEWS_PROVIDER=finnhub`, `NEWS_API_KEY` | Real headlines with source URLs |
| Financial Modeling Prep | `ECONOMIC_CALENDAR_PROVIDER=fmp`, `ECONOMIC_CALENDAR_API_KEY` | Economic calendar |
| MT5 / IBKR / Alpaca | – | Not implemented: documented stubs that refuse to place orders |

Every integration's real state (CONNECTED, DEMO, NOT CONFIGURED, DISCONNECTED, ERROR)
is shown on **System Status** and in the top bar; failures are never hidden.

## Security

* No accounts or login by design: **single user on localhost**. The API binds to
  `127.0.0.1`; Docker publishes ports on `127.0.0.1` only. Do not expose it to a network
  without an authenticating reverse proxy.
* Secrets live only in the server environment (`.env`, `.secrets.env`), both git-ignored.
  The UI shows "configured" and the last four characters, never the key.
* CORS allow-list, WebSocket origin check, per-route rate limits (stricter for AI and
  backtests), request validation, CSV formula-injection protection, image re-encoding on
  upload, structured errors without stack traces, security headers and a production CSP.
* Audit log of signals, AI calls, orders, risk events, settings changes and errors.
* Live execution requires three independent gates and is impossible in this build.

## Deployment

NEXUS is designed to run on your own machine. `docker compose up --build` runs
API + web + Redis with a persistent volume for the database and secrets. See
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for production builds, data locations,
backups and the steps to connect real providers.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| "The NEXUS API is not reachable" | Start the backend (`npm run dev` starts both); check port 8000 is free |
| `npm run dev` says setup is missing | Run `npm run setup` once |
| Everything shows DEMO | Expected without keys. Add keys in Settings or `.env`; check **System Status** |
| Signals are all NO_TRADE | Normal: filters are strict. A fresh database has no setup memory yet — run `npm run seed` or wait for the background memory build |
| Live updates stalled (Stream dot not green) | The UI falls back to polling; check `CORS_ORIGINS` contains the web origin |
| Claude/Gemini show ERROR | Check the key, model names and network access on System Status |
| Port already in use | Stop the other process, or change `API_PORT` (and `NEXUS_API_URL` for the web app), or run the web app with `npx next dev --port 3001` in `apps/web` and add that origin to `CORS_ORIGINS` |
| Database problems | Stop the app and delete `data/nexus.db` (DEMO data can be re-seeded) |

---

Research tool only. Not financial advice. Past or simulated performance does not
guarantee future results.
