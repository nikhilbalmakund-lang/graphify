# CLAUDE.md — working on NEXUS Trading Intelligence

Guidance for coding agents (and humans) changing this repository. Read
`README.md` for the product overview and `docs/` for subsystem details.

## Non-negotiable rules

1. **Never fabricate** market data, news, economic events, AI results or backtest
   performance. When real data is unavailable, use DEMO data and label it.
2. **Every value carries provenance**: LIVE / DEMO / IMPORTED / BACKTEST / PAPER /
   IMAGE ANALYSIS (`is_demo`, `provider`, `data_mode` fields; `ModeBadge` in the UI).
3. **Scores are not probabilities.** Render `SIGNAL SCORE NN/100`. Show a probability
   only from `calibrated_probability`, which exists only when the outcome model passed
   out-of-sample calibration (`quant/ml/calibration.py`).
4. **Separation of layers:** DATA (`market_data`) · QUANT (`quant`) · AI (`ai`) ·
   RISK (`risk`) · EXECUTION (`paper_trading`) · UI (`apps/web`). AI must not write to
   the database, place orders or bypass the risk engine. AI tools are read-only
   (`ai/orchestration/tools.py`); there is no order tool and there must never be one.
5. **The risk engine has the final veto** over every order (manual, signal, automated).
6. **Live trading stays off.** Three gates: `LIVE_TRADING_ENABLED`, the UI safety
   switch, an implemented live broker. `paper_trading/broker/live.py` adapters refuse
   to trade. Never send a real order from paper mode.
7. **Secrets stay server-side.** Never return keys to the browser, log them or commit
   them (`.env`, `.secrets.env` are git-ignored). Never return stack traces to clients.
8. No authentication/multi-user features: this is a single-user localhost app.

## Layout

```
apps/web/                 Next.js App Router UI (pages in app/<route>/view.tsx)
  components/ui           shadcn-style primitives on radix-ui
  components/layout       shell, top bar, ticker, palette, providers (SWR, live WS)
  components/{market,signals,charts,panels,backtest,ai,common}
  lib/                    api client, formatting, live WebSocket client, constants
packages/shared-types/    hand-written API types (index.ts) + generated api.d.ts
services/                 Python packages (PYTHONPATH = services and services/api)
  api/app/                FastAPI: api/ routes, services/, models/, core/, websocket/, cli.py
  market_data/ quant/ ai/ risk/ backtesting/ paper_trading/   each with tests/
database/                 alembic.ini + migrations (run from repo root config)
scripts/                  py.mjs (python launcher), setup/dev/start, e2e-api
```

## Commands

| Task | Command |
| --- | --- |
| First-time setup | `npm run setup` |
| Run (API :8000 + web :3000) | `npm run dev` · with DEMO seed: `npm run demo` |
| Python in project env | `node scripts/py.mjs <args>` (cwd `services`, correct PYTHONPATH) |
| Backend tests | `npm run test:api` (pytest) |
| Web unit tests | `npm run test:web` (vitest) |
| E2E | `npm run build && npm run test:e2e` (Playwright; isolated DEMO DB on :8000/:3100) |
| Lint | `npm run lint` (ruff check + format check, ESLint) |
| Types | `npm run typecheck` (mypy, tsc) |
| Migrations | `npm run db:migrate`; new revision: `cd services && PYTHONPATH=.:api .venv/bin/alembic -c ../database/alembic.ini revision --autogenerate -m "..."` then check `alembic check` |
| API types for the UI | `npm run gen:types` |

## Conventions

* Python 3.11, Pydantic v2 models at every boundary, SQLAlchemy 2 async, ruff line 110,
  mypy clean. Deterministic code: no wall-clock reads inside quant/backtest logic
  (inject clocks), no randomness without fixed seeds.
* Version every behavioural component (`FEATURE_VERSION`, `REGIME_VERSION`,
  `SIGNAL_ENGINE_VERSION`, `RISK_ENGINE_VERSION`, backtest `ENGINE_VERSION`, strategy
  versions, prompt `name@version` with date). Bump the version when behaviour changes;
  signals store the versions they were produced with.
* Prompts live in `ai/prompts/registry.py`; outputs are validated against strict JSON
  schemas (`ai/schemas/outputs.py`) and then deterministically (`ai/critic/validation.py`:
  grounded prices, no certainty language, R:R sanity, news risk).
* Backtests: strategies read bars only through `BarView` (look-ahead raises), fills at
  next bar open, stop-first inside a bar. Never hide losing periods or losing trades.
* UI: Tailwind tokens from `styles/tokens.css` (`bg-panel`, `text-muted`, `text-up`…),
  `Panel`/`PanelHeader`, `DataBlock` for loading/error/empty states, `useApi` (SWR) for
  GETs, `post/put/patch/del` from `lib/api.ts`. Pages: `app/<route>/page.tsx` exports
  metadata and renders `./view.tsx`. Respect `react-hooks` lint rules (no setState in
  effects: use keys, derived state or event handlers).
* Tests accompany changes: backend unit/integration tests in each package's `tests/`,
  web unit tests in `apps/web/tests/unit`, flows in `apps/web/tests/e2e`.

## Before finishing a change

`npm run lint && npm run typecheck && npm test`, plus `npm run build` for UI changes and
`npm run test:e2e` for user-flow changes. Update docs when behaviour changes.
