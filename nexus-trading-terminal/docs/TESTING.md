# Testing

| Suite | Location | Command | Count |
| --- | --- | --- | --- |
| Market data | `services/market_data/tests` | `npm run test:api` | 17 |
| Quant (indicators, structure, regime, signals, memory/ML) | `services/quant/tests` | 〃 | 52 |
| Risk | `services/risk/tests` | 〃 | 19 |
| AI (fake provider clients, schemas, consensus, critic, tools) | `services/ai/tests` | 〃 | 21 |
| Backtesting | `services/backtesting/tests` | 〃 | 19 |
| Paper trading | `services/paper_trading/tests` | 〃 | 9 |
| API integration (FastAPI TestClient, temp DB, DEMO mode) | `services/api/app/tests` | 〃 | 23 |
| Web unit (vitest) | `apps/web/tests/unit` | `npm run test:web` | 17 |
| End-to-end (Playwright, desktop + Pixel 7) | `apps/web/tests/e2e` | `npm run build && npm run test:e2e` | 11 |

`npm test` runs the backend and web unit suites. Counts are from the last full run.

## What is covered

* **Determinism & causality:** indicators and structure give identical results on
  truncated data (no repainting), swing history is exact at any past bar, the demo price
  model is reproducible.
* **No look-ahead:** `BarView` raises on future access; backtests fill on the next bar,
  stop-first inside a bar, gaps at the open.
* **Signal rules:** stops only from structure, NO_TRADE without evidence, filters block,
  MTF contradiction; in the UI (E2E) the score is never shown as a probability.
* **Calibration gate:** probabilities only when out-of-sample criteria pass.
* **Risk:** every limit, sizing modes, correlation, kill switch, live-trading gate.
* **AI:** strict schemas, invented prices rejected, certainty language flagged, AI can
  only downgrade, tools are read-only, provider errors and refusals handled (fake clients;
  no network).
* **API:** DEMO labelling, structured errors without stack traces, security headers,
  write-only secrets, CSV import validation, image validation, scanner de-duplication,
  daily AI cap, WebSocket hello, OpenAPI coverage.
* **E2E:** dashboard labelling, keyboard shortcuts and command palette, system status,
  signal pipeline, scanner, backtest report, paper order + kill switch, journal,
  write-only keys, live-trading gate, mobile bottom navigation.

## E2E isolation

`scripts/e2e-api.mjs` starts the API with a fresh database under `data/e2e/`, a
non-existent env file and its own secrets file, so the suite always runs in DEMO mode and
never touches your `.env`, `.secrets.env` or `data/nexus.db`. Ports 8000 and 3100 must be
free. Playwright uses the Chromium it was installed with (`npx playwright install
chromium` once on a new machine).

## Static checks

`npm run lint` (ruff + format check, ESLint with Next/React rules), `npm run typecheck`
(mypy with the Pydantic plugin, `tsc --noEmit`), `npm run security` (bandit, pip-audit,
`npm audit --omit=dev`).
