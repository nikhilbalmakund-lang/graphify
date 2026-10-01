# API

FastAPI serves interactive documentation at `http://127.0.0.1:8000/docs`
(Swagger) and `/redoc`; the machine-readable schema is `/openapi.json`
(exported to `packages/shared-types/openapi.json` by `npm run gen:types`).

The browser calls the API through the Next.js proxy (`/api/*`), so the same paths
work at `http://localhost:3000/api/...`.

## Conventions

* JSON in and out; Pydantic validation on every body and query parameter.
* Errors: `{"error": {"code", "message", "request_id", "details"}}` with a fitting HTTP
  status. Codes: `VALIDATION_ERROR`, `NOT_FOUND`, `INVALID_SYMBOL`, `INSUFFICIENT_DATA`,
  `INVALID_MARKET_DATA`, `STALE_MARKET_DATA`, `DATA_PROVIDER_UNAVAILABLE`,
  `AI_PROVIDER_UNAVAILABLE`, `RISK_LIMIT_REACHED`, `BACKTEST_ERROR`, `BROKER_ERROR`,
  `LIVE_TRADING_DISABLED`, `RATE_LIMITED`, `INTERNAL_ERROR`. Stack traces are never returned.
* Every response carries `X-Request-ID`; security headers are set on all responses.
* Rate limits per minute (configurable): AI 20, backtests 10, market data 600, other 300.
* Timestamps are ISO-8601 UTC. Candles are `[unix_seconds, open, high, low, close, volume]`.

## Endpoints

| Group | Endpoints |
| --- | --- |
| Health & system | `GET /health` · `GET /api/system/status` · `GET /api/system/events` |
| Settings | `GET /api/settings` · `PUT /api/settings/{category}` (risk, signals, ai, markets, paper, appearance, notifications, data) · `PUT /api/settings-secrets` (write-only keys) · `POST /api/settings/live-trading-switch` · `GET /api/settings/export` · `POST /api/settings/import` |
| Alerts & notifications | `GET/POST /api/alerts` · `PATCH/DELETE /api/alerts/{id}` · `GET /api/notifications` · `POST /api/notifications/read` |
| Search | `GET /api/search?q=` (assets, signals, strategies, journal, news) |
| Market | `GET /api/market/assets` · `quotes` · `candles?symbol&timeframe&limit` · `features` · `regime` · `structure` · `mtf` · `overlays` · `overview` · `status` · `POST /api/market/import` (CSV) · `GET /api/market/imports` |
| Signals | `GET /api/signals?status&symbol&direction&active&limit` · `POST /api/signals/generate` · `GET /api/signals/stats` · `GET /api/signals/export.csv` · `GET /api/signals/{id}` · `POST /api/signals/{id}/explain` · `GET /api/signals/{id}/similar` · `POST /api/signals/{id}/paper` |
| Scanner & history | `GET /api/scanner?timeframe&min_score&min_rr&max_vol_percentile&exclude_news_risk&regime&only_signals&sort` · `GET /api/history/conditions` · `GET /api/history/memory` |
| Paper trading | `GET /api/paper-trading` · `POST /api/paper-trading/orders` · `DELETE /api/paper-trading/orders/{id}` · `POST /api/paper-trading/positions/{id}/close?lots` · `POST /api/paper-trading/kill-switch` · `POST /api/paper-trading/reset` · `GET /api/paper-trading/export.csv` |
| Portfolio & risk | `GET /api/portfolio` · `GET /api/risk/status` · `GET /api/analytics/performance` |
| Journal | `GET /api/journal?symbol&strategy&result&regime&entry_type&start&end` · `POST /api/journal` (manual trade) · `PATCH /api/journal/{id}` · `GET /api/journal/export.csv` |
| Research | `GET /api/strategies` · `GET /api/strategies/performance` · `POST /api/backtests` · `POST /api/backtests/walk-forward` · `GET /api/backtests` · `GET /api/backtests/{id}` · `GET /api/backtests/{id}/trades.csv` · `POST /api/strategies/ml/train` · `GET /api/strategies/ml` |
| Content | `GET /api/news` · `POST /api/news/refresh` · `GET /api/calendar` · `GET /api/calendar/risk/{symbol}` · `GET /api/heatmap` · `GET /api/psychology` · `GET /api/correlations` |
| AI | `POST /api/ai/chat` · `POST /api/ai/analyze` · `POST /api/ai/research` · `POST /api/ai/chart-scan` (multipart image) · `GET/POST /api/ai/briefing` · `POST /api/ai/history-query` · `GET /api/ai/analytics` · `GET /api/ai/prompts` · `GET /api/ai/status` |

## WebSocket `/ws`

Connect from an origin listed in `CORS_ORIGINS`. Messages are
`{"topic": ..., "data": ...}` with topics `quotes`, `signals`, `notifications`,
`paper`, `system`, `backtests`. Clients receive every topic unless they send
`{"action": "subscribe", "topics": [...]}`; `{"action": "ping"}` returns a PONG.

## Examples

```bash
curl -s localhost:8000/api/market/quotes?symbols=XAUUSD,BTCUSD
curl -s -X POST localhost:8000/api/signals/generate -H 'content-type: application/json' \
     -d '{"symbol":"XAUUSD","timeframe":"15m","use_ai":true}'
curl -s -X POST localhost:8000/api/backtests -H 'content-type: application/json' \
     -d '{"symbol":"EURUSD","timeframe":"1H","strategy":"TrendFollowing"}'
curl -s -X POST localhost:8000/api/paper-trading/orders -H 'content-type: application/json' \
     -d '{"symbol":"BTCUSD","side":"BUY","type":"MARKET","lots":0.05,"stop_loss":60000,"take_profits":[{"price":68000,"fraction":1}]}'
```
