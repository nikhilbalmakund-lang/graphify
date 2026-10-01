# Deployment

NEXUS is a **single-user application without authentication**. Run it on your own
machine (or a private host reachable only by you). Never expose ports 3000/8000 to a
network without an authenticating reverse proxy in front.

## Local production build

```bash
npm run setup          # once
npm run build          # Next.js production build
npm start              # API (no reload) on :8000 + `next start` on :3000
```

## Docker Compose

```bash
cp .env.example .env   # optional; add keys here or later in Settings
docker compose up --build -d
docker compose run --rm api python -m app.cli seed     # optional DEMO seed
docker compose logs -f api
```

Services: `api` (FastAPI, port 127.0.0.1:8000), `web` (Next.js standalone, port
127.0.0.1:3000; proxies `/api` to `http://api:8000` server-side), `redis` (cache, no
persistence). Volume `nexus-data` holds the SQLite database and `.secrets.env`.
Both application images run as a non-root user and define health checks.

The browser opens the live-update WebSocket directly at `ws://<host>:8000/ws`; if you
serve the UI from another origin, add it to `CORS_ORIGINS`.

## Data and backups

| Item | Local | Docker |
| --- | --- | --- |
| Database | `data/nexus.db` | volume `nexus-data:/app/data/nexus.db` |
| Keys entered in Settings | `.secrets.env` (0600) | `/app/data/.secrets.env` |
| Configuration | `.env` | `.env` via `env_file` |

Back up by stopping the API and copying the database file (or
`docker compose cp api:/app/data/nexus.db ./backup.db`). Settings can also be exported
as JSON from Settings (no secrets included).

## Enabling real integrations

1. **Market data:** `MARKET_DATA_PROVIDER=twelvedata`, `MARKET_DATA_API_KEY=...`; restart.
   System Status shows CONNECTED (or ERROR with the provider message). Map symbols your
   plan names differently with `MARKET_DATA_SYMBOL_MAP`. If the provider fails, NEXUS
   reports it and falls back to DEMO data, clearly labelled.
2. **Claude:** `ANTHROPIC_API_KEY=...` (Settings or `.env`); optionally change
   `CLAUDE_MODEL_FAST` / `CLAUDE_MODEL_STRONG`. Keys entered in Settings apply without a restart.
3. **Gemini:** `GEMINI_API_KEY=...`; optionally `GEMINI_MODEL_FAST` / `GEMINI_MODEL_STRONG`.
4. **News / calendar:** `NEWS_PROVIDER=finnhub` + `NEWS_API_KEY`;
   `ECONOMIC_CALENDAR_PROVIDER=fmp` + `ECONOMIC_CALENDAR_API_KEY`; restart.
5. **Paper trading** works out of the box; adjust risk and paper settings in Settings.
6. **Live broker:** not implemented. A live adapter must implement `BrokerProvider`
   (`paper_trading/broker/base.py`), replace the refusing stub in `broker/live.py`, pass a
   dedicated test suite against the broker's sandbox, and still requires
   `LIVE_TRADING_ENABLED=true` plus the UI safety switch. Do this only with the broker's
   paper/sandbox environment first.

## Operations

* Health: `GET /health` (DB, cache, data mode, AI status). Detailed: System Status page.
* Logs: structured JSON to stdout (`LOG_JSON=true`), with request and signal IDs;
  secrets are redacted.
* Audit trail: `system_events` table (System Status → Audit log).
