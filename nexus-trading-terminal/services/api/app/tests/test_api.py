"""API integration tests (DEMO mode, no network, no API keys)."""

from __future__ import annotations

import io
from datetime import timedelta

from PIL import Image

from app.tests.conftest import FIXED_NOW


def test_health_and_status(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["mode"] == "DEMO" and h["market_data"] == "DEMO"
    st = client.get("/api/system/status").json()
    comps = {x["name"]: x["status"] for x in st["components"]}
    assert comps["Market Data"] == "DEMO"
    assert comps["Claude"] == "NOT_CONFIGURED" and comps["Gemini"] == "NOT_CONFIGURED"
    assert comps["AI Demo Fallback"] == "DEMO" and comps["Paper Broker"] == "CONNECTED"
    assert comps["News"] == "DEMO" and comps["Economic Calendar"] == "DEMO"
    assert st["live_trading"]["allowed"] is False and st["trading_mode"] == "PAPER"
    assert st["versions"]["signal_engine"] == "1.0.0"


def test_request_id_and_security_headers(client):
    r = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123" and r.headers["X-Content-Type-Options"] == "nosniff"


def test_errors_are_structured_without_stack_traces(client):
    r = client.get("/api/market/candles", params={"symbol": "NOPE"})
    body = r.json()
    assert r.status_code == 404 and body["error"]["code"] == "INVALID_SYMBOL" and body["error"]["request_id"]
    v = client.get("/api/market/candles", params={"symbol": "XAUUSD", "limit": 1})
    assert v.status_code == 422 and v.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "Traceback" not in v.text
    bad_tf = client.get("/api/market/candles", params={"symbol": "XAUUSD", "timeframe": "7m"})
    assert bad_tf.status_code == 422


def test_market_endpoints_are_labelled_demo(client):
    assets = client.get("/api/market/assets").json()
    assert {a["symbol"] for a in assets} >= {"XAUUSD", "EURUSD", "BTCUSD", "NAS100", "USOIL"}
    quotes = client.get("/api/market/quotes").json()
    assert len(quotes) == 10 and all(q["is_demo"] and q["provider"] == "demo" for q in quotes)
    c = client.get("/api/market/candles", params={"symbol": "gold", "timeframe": "15m", "limit": 200}).json()
    assert c["symbol"] == "XAUUSD" and c["is_demo"] and c["mode"] == "DEMO" and len(c["bars"]) == 200
    assert c["data_quality"]["usable"]
    f = client.get("/api/market/features", params={"symbol": "EURUSD", "timeframe": "1H"}).json()
    assert f["feature_version"] == "1.0.0" and -100 <= f["trend_score"] <= 100
    assert client.get("/api/market/regime", params={"symbol": "EURUSD"}).json()["regime"]
    s = client.get("/api/market/structure", params={"symbol": "EURUSD", "timeframe": "1H"}).json()
    assert "heuristic" in s["heuristic_note"].lower()
    m = client.get("/api/market/mtf", params={"symbol": "BTCUSD", "timeframe": "15m"}).json()
    assert len(m["views"]) == 7 and -1 <= m["alignment"] <= 1
    ov = client.get("/api/market/overview").json()
    assert ov["is_demo"] and len(ov["cards"]) == 10 and all(card["status"] == "OK" for card in ov["cards"])
    o = client.get("/api/market/overlays", params={"symbol": "XAUUSD", "timeframe": "15m"}).json()
    assert o["lines"]["ema20"] and o["panes"]["rsi14"]


def test_signal_pipeline_without_evidence_is_no_trade(client):
    r = client.post("/api/signals/generate", json={"symbol": "XAUUSD", "timeframe": "15m"}).json()
    assert r["is_demo"] and r["data_mode"] == "DEMO" and 0 <= r["score"] <= 100
    assert r["versions"]["signal_engine"] == "1.0.0" and r["versions"]["features"] == "1.0.0"
    if r["proposed_direction"] != "NO_TRADE" and r["entry_price"] is not None:
        assert r["direction"] == "NO_TRADE"  # empty setup memory -> evidence filter blocks
        assert any("Historical evidence" in x for x in r["no_trade_reasons"])
    detail = client.get(f"/api/signals/{r['id']}").json()
    assert detail["analysis"]["features"] and detail["analysis"]["mtf"]["views"]
    assert client.get("/api/signals/does-not-exist").status_code == 404


def test_signals_can_become_active_and_go_to_paper(client):
    client.put(
        "/api/settings/signals",
        json={
            "min_historical_samples": 0,
            "min_score": 0,
            "min_score_margin": 0,
            "min_rr": 0.5,
            "block_on_mtf_contradiction": False,
            "max_spread_atr": 2,
            "max_vol_percentile": 100,
        },
    )
    client.put("/api/settings/risk", json={"min_rr": 0.5, "max_spread_atr": 2.0})
    active = None
    for sym in (
        "XAUUSD",
        "EURUSD",
        "BTCUSD",
        "GBPUSD",
        "NAS100",
        "USDJPY",
        "ETHUSD",
        "SPX500",
        "US30",
        "USOIL",
    ):
        r = client.post(
            "/api/signals/generate", json={"symbol": sym, "timeframe": "15m", "force": True}
        ).json()
        assert r["ai_summary"] is None or r["ai_summary"]["agreement"] == "UNAVAILABLE"
        if r["status"] == "ACTIVE":
            active = r
            break
    assert active is not None, "expected at least one ACTIVE demo signal with relaxed filters"
    assert active["direction"] in ("LONG", "SHORT") and active["stop"] and len(active["targets"]) == 3
    assert active["risk_decision"]["approved"] is True
    assert active["ai_summary"]["note"].startswith("AI review unavailable")
    listed = client.get("/api/signals", params={"active": True}).json()
    assert any(s["id"] == active["id"] for s in listed)
    journal = client.get("/api/journal", params={"entry_type": "SIGNAL"}).json()
    assert any(j["signal_id"] == active["id"] for j in journal)
    paper = client.post(f"/api/signals/{active['id']}/paper").json()
    assert paper["simulated"] and paper["order"]["is_paper"] and paper["risk"]["approved"]
    csv = client.get("/api/signals/export.csv")
    assert csv.status_code == 200 and csv.text.startswith("id,created_at,symbol")


def test_scanner_does_not_stack_signals_on_open_setups(client, monkeypatch):
    from market_data.models import Timeframe

    container = client.container
    active = client.get("/api/signals", params={"active": True}).json()
    assert active, "previous test leaves an ACTIVE signal"
    sig = active[0]

    async def no_signal_for_this_bar(*_args, **_kwargs):
        return None  # pretend a new bar closed since the open signal was issued

    monkeypatch.setattr(container.signals, "_existing", no_signal_for_this_bar)
    created = client.portal.call(
        container.signals.scan_new_bars, [sig["symbol"]], Timeframe(sig["timeframe"])
    )
    assert created == 0
    before = client.get("/api/signals", params={"symbol": sig["symbol"], "limit": 1000}).json()
    via_scanner = client.portal.call(
        lambda: container.signals.generate(sig["symbol"], Timeframe(sig["timeframe"]), source="scanner")
    )
    open_ids = {s["id"] for s in before if s["status"] in ("ACTIVE", "TRIGGERED", "TP1_HIT", "TP2_HIT")}
    assert via_scanner["id"] in open_ids
    after = client.get("/api/signals", params={"symbol": sig["symbol"], "limit": 1000}).json()
    assert len(after) == len(before)


def test_scanner_filters_and_labels(client):
    r = client.get("/api/scanner", params={"timeframe": "15m", "sort": "score"}).json()
    assert r["is_demo"] and "not predictions" in r["note"]
    scores = [row["score"] for row in r["rows"]]
    assert scores == sorted(scores, reverse=True)
    high = client.get("/api/scanner", params={"min_score": 99.9}).json()
    assert all(row["score"] >= 99.9 for row in high["rows"])


def test_paper_trading_requires_stop_and_respects_risk(client):
    no_stop = client.post("/api/paper-trading/orders", json={"symbol": "EURUSD", "side": "BUY", "lots": 0.1})
    assert no_stop.status_code == 409 and no_stop.json()["error"]["code"] == "RISK_LIMIT_REACHED"
    q = client.get("/api/market/quotes", params={"symbols": "EURUSD"}).json()[0]
    too_big = client.post(
        "/api/paper-trading/orders",
        json={"symbol": "EURUSD", "side": "BUY", "lots": 40, "stop_loss": q["bid"] - 0.01},
    )
    assert too_big.status_code == 409 and "reasons" in too_big.json()["error"]["details"]
    ok = client.post(
        "/api/paper-trading/orders",
        json={
            "symbol": "EURUSD",
            "side": "BUY",
            "lots": 0.1,
            "stop_loss": round(q["bid"] - 0.003, 5),
            "take_profits": [{"price": round(q["ask"] + 0.006, 5), "fraction": 1.0}],
        },
    )
    assert ok.status_code == 200, ok.text
    order = ok.json()["order"]
    assert order["status"] == "FILLED" and order["is_paper"]
    ov = client.get("/api/paper-trading").json()
    assert ov["label"].startswith("PAPER TRADING") and any(
        p["id"] == order["position_id"] for p in ov["positions"]
    )
    closed = client.post(f"/api/paper-trading/positions/{order['position_id']}/close").json()
    assert closed["position"]["status"] == "CLOSED" and closed["simulated"]
    j = client.get("/api/journal", params={"entry_type": "PAPER_TRADE"}).json()
    assert any(
        x["position_id"] == order["position_id"] and x["result"] in ("WIN", "LOSS", "BREAKEVEN") for x in j
    )
    pf = client.get("/api/portfolio").json()
    assert pf["label"].startswith("PAPER PORTFOLIO") and "daily_pnl" in pf["summary"]
    assert client.get("/api/paper-trading/export.csv").status_code == 200


def test_kill_switch_halts_trading(client):
    assert client.post("/api/paper-trading/kill-switch", json={"active": True}).json()["kill_switch"] is True
    q = client.get("/api/market/quotes", params={"symbols": "XAUUSD"}).json()[0]
    r = client.post(
        "/api/paper-trading/orders",
        json={"symbol": "XAUUSD", "side": "BUY", "lots": 0.01, "stop_loss": q["bid"] - 5},
    )
    assert r.status_code == 409 and any("kill_switch" in x for x in r.json()["error"]["details"]["reasons"])
    assert client.get("/api/risk/status").json()["state"] == "HALTED"
    client.post("/api/paper-trading/kill-switch", json={"active": False})
    events = client.get("/api/system/events", params={"event_type": "KILL_SWITCH"}).json()
    assert len(events) >= 2


def test_journal_manual_trade_and_notes(client):
    body = {
        "symbol": "XAUUSD",
        "direction": "LONG",
        "entry_time": (FIXED_NOW - timedelta(hours=5)).isoformat(),
        "exit_time": (FIXED_NOW - timedelta(hours=1)).isoformat(),
        "entry_price": 2300.0,
        "exit_price": 2310.0,
        "stop": 2295.0,
        "lots": 0.5,
        "fees": 2.0,
        "notes": "manual entry",
    }
    j = client.post("/api/journal", json=body).json()
    assert (
        j["entry_type"] == "MANUAL_TRADE"
        and j["pnl"] == 498.0
        and j["r_multiple"] == round(498 / 250, 4)
        and j["result"] == "WIN"
    )
    p = client.patch(f"/api/journal/{j['id']}", json={"notes": "=cmd()", "tags": ["review"]}).json()
    assert p["tags"] == ["review"]
    csv = client.get("/api/journal/export.csv").text
    assert "'=cmd()" in csv  # formula injection neutralised
    bad = client.post(
        "/api/journal", json={**body, "exit_time": (FIXED_NOW - timedelta(hours=9)).isoformat()}
    )
    assert bad.status_code == 422


def test_backtest_and_walk_forward(client):
    start = (FIXED_NOW - timedelta(days=120)).isoformat()
    r = client.post(
        "/api/backtests",
        json={
            "symbol": "XAUUSD",
            "timeframe": "1H",
            "strategy": "Breakout",
            "start": start,
            "end": FIXED_NOW.isoformat(),
        },
    )
    assert r.status_code == 200, r.text
    bt = r.json()
    assert bt["is_demo"] and "DEMO" in bt["data_label"] and bt["metrics"]["total_trades"] == len(bt["trades"])
    assert bt["result"]["equity_curve"] and any("DEMO DATA" in w for w in bt["warnings"])
    assert client.get(f"/api/backtests/{bt['id']}/trades.csv").status_code == 200
    assert any(b["id"] == bt["id"] for b in client.get("/api/backtests").json())
    wf = client.post(
        "/api/backtests/walk-forward",
        json={
            "backtest": {
                "symbol": "EURUSD",
                "timeframe": "1H",
                "strategy": "Breakout",
                "start": (FIXED_NOW - timedelta(days=240)).isoformat(),
                "end": FIXED_NOW.isoformat(),
            },
            "train_bars": 1500,
            "validation_bars": 400,
            "test_bars": 400,
            "max_windows": 2,
        },
    )
    assert wf.status_code == 200, wf.text
    res = wf.json()["result"]
    assert len(res["windows"]) == 2 and "overfitting" in res
    bad = client.post("/api/backtests", json={"symbol": "XAUUSD", "timeframe": "1H", "strategy": "Nope"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "BACKTEST_ERROR"
    perf = client.get("/api/strategies/performance").json()
    assert any(r["strategy"] == "Breakout" and r["source"] == "BACKTEST" for r in perf["rows"])


def test_news_and_calendar_are_demo_and_never_fabricate_urls(client):
    news = client.get("/api/news").json()
    assert news and all(
        n["is_demo"] and n["url"] is None and n["headline"].startswith("[DEMO]") for n in news
    )
    assert all(n["sentiment_source"] in (None, "rule-based") for n in news)
    cal = client.get("/api/calendar", params={"hours_ahead": 168}).json()
    assert cal and all(
        e["is_demo"] and e["event"].startswith("[DEMO]") and "synthetic" in e["source"] for e in cal
    )
    assert client.get("/api/calendar", params={"impact": "EXTREME"}).status_code == 422
    risk = client.get("/api/calendar/risk/EURUSD").json()
    assert risk["available"] and risk["is_demo"]


def test_heatmap_psychology(client):
    hm = client.get("/api/heatmap", params={"asset_class": "CRYPTO"}).json()
    assert {r["symbol"] for r in hm["rows"]} == {"BTCUSD", "ETHUSD"}
    ps = client.get("/api/psychology").json()
    assert "inferred from measurable market variables" in ps["disclaimer"]
    assert ps["breadth"]["instruments"] == 10 and ps["correlation"]["symbols"]


def test_ai_endpoints_in_demo_mode(client):
    chat = client.post("/api/ai/chat", json={"question": "What is happening with Gold?"}).json()
    assert chat["is_ai"] is False and chat["provider"] == "rule-based" and chat["tool_trace"]
    assert {t["name"] for t in chat["tool_trace"]} >= {"get_market_data", "get_indicators", "get_structure"}
    assert chat["answer"]["facts"] and "no AI model" in chat["answer"]["interpretation"][0]
    br = client.post("/api/ai/briefing", params={"session": "INTRADAY", "force": True}).json()["briefing"]
    assert br["is_ai"] is False and br["is_demo_data"] and br["content"]["theme"]
    assert client.get("/api/ai/briefing").json()["briefing"]["id"] == br["id"]
    research = client.post("/api/ai/research", json={"symbol": "EURUSD", "timeframe": "1H"}).json()
    assert {s["name"] for s in research["report"]["scenarios"]} == {"BULLISH", "BEARISH", "NO_TRADE"}
    hq = client.post("/api/ai/history-query", json={"symbol": "EURUSD", "timeframe": "1H", "k": 20}).json()
    assert "summary" in hq and hq["is_demo"]
    analytics = client.get("/api/ai/analytics").json()
    assert "does not demonstrate" in analytics["disclaimer"]
    assert len(client.get("/api/ai/prompts").json()) >= 7


def test_chart_scanner_validation(client):
    buf = io.BytesIO()
    Image.new("RGB", (64, 32), "black").save(buf, format="PNG")
    r = client.post(
        "/api/ai/chart-scan",
        files={"file": ("chart.png", buf.getvalue(), "image/png")},
        data={"symbol": "XAUUSD"},
    ).json()
    assert (
        r["available"] is False and "IMAGE ANALYSIS" in r["label"] and r["market_data"]["symbol"] == "XAUUSD"
    )
    assert r["image"]["width"] == 64
    bad = client.post("/api/ai/chart-scan", files={"file": ("x.png", b"not an image", "image/png")})
    assert bad.status_code == 422
    wrong = client.post("/api/ai/chart-scan", files={"file": ("x.gif", b"GIF89a", "image/gif")})
    assert wrong.status_code == 422


def test_settings_and_secrets_never_echo_keys(client):
    s = client.get("/api/settings").json()
    assert s["settings"]["risk"]["max_risk_per_trade"] == 0.01 and all(
        not x["configured"] for x in s["secrets"]
    )
    bad = client.put("/api/settings/risk", json={"max_risk_per_trade": 0.5})
    assert bad.status_code == 422
    up = client.put("/api/settings/appearance", json={"accent": "purple"}).json()
    assert up["values"]["accent"] == "purple"
    secret = "sk-ant-test-0000000000000000wxyz"
    r = client.put("/api/settings-secrets", json={"values": {"ANTHROPIC_API_KEY": secret}})
    assert r.status_code == 200 and secret not in r.text
    st = {x["key"]: x for x in r.json()}
    assert st["ANTHROPIC_API_KEY"]["configured"] and st["ANTHROPIC_API_KEY"]["hint"] == "****wxyz"
    assert secret not in client.get("/api/settings").text
    client.put("/api/settings-secrets", json={"values": {"ANTHROPIC_API_KEY": None}})
    assert client.put("/api/settings-secrets", json={"values": {"EVIL": "x"}}).status_code == 422
    exported = client.get("/api/settings/export").json()
    assert "live_trading" not in exported["settings"] and "secrets" not in exported
    live = client.post("/api/settings/live-trading-switch", json={"on": True}).json()
    assert live["ui_switch_on"] and live["allowed"] is False
    client.post("/api/settings/live-trading-switch", json={"on": False})


def test_alerts_notifications_search(client):
    a = client.post(
        "/api/alerts",
        json={"type": "PRICE_LEVEL", "symbol": "XAUUSD", "condition": {"direction": "above", "price": 1.0}},
    )
    assert a.status_code == 200
    assert (
        client.post(
            "/api/alerts", json={"type": "PRICE_LEVEL", "symbol": "XAUUSD", "condition": {}}
        ).status_code
        == 422
    )
    alerts = client.get("/api/alerts").json()
    assert any(x["id"] == a.json()["id"] for x in alerts)
    client.patch(f"/api/alerts/{a.json()['id']}", json={"enabled": False})
    assert client.delete(f"/api/alerts/{a.json()['id']}").json()["deleted"]
    notes = client.get("/api/notifications").json()
    assert isinstance(notes, list)
    res = client.get("/api/search", params={"q": "gold"}).json()
    assert res["assets"][0]["symbol"] == "XAUUSD"


def test_import_csv_validates(client):
    good = "timestamp,open,high,low,close,volume\n" + "\n".join(
        f"2025-01-01T{h:02d}:00:00Z,{100 + h},{101 + h},{99 + h},{100.5 + h},10" for h in range(10)
    )
    r = client.post(
        "/api/market/import",
        files={"file": ("d.csv", good, "text/csv")},
        data={"symbol": "XAUUSD", "timeframe": "1H"},
    )
    assert r.status_code == 200 and r.json()["rows"] == 10
    bad = good.replace("101,99", "90,99", 1)
    r2 = client.post(
        "/api/market/import",
        files={"file": ("d.csv", bad, "text/csv")},
        data={"symbol": "XAUUSD", "timeframe": "1H"},
    )
    assert r2.status_code == 422 and r2.json()["error"]["code"] == "INVALID_MARKET_DATA"
    assert client.get("/api/market/imports").json()[0]["rows"] == 10


def test_websocket_hello(client):
    with client.websocket_connect("/ws") as ws:
        msg = ws.receive_json()
        assert msg["topic"] == "system" and msg["data"]["mode"] == "DEMO"
        ws.send_json({"action": "ping"})
        assert ws.receive_json()["data"]["event"] == "PONG"


def test_openapi_documents_core_routes(client):
    spec = client.get("/openapi.json").json()
    for path in (
        "/api/market/assets",
        "/api/market/candles",
        "/api/market/features",
        "/api/market/regime",
        "/api/signals",
        "/api/signals/{signal_id}",
        "/api/scanner",
        "/api/news",
        "/api/calendar",
        "/api/heatmap",
        "/api/portfolio",
        "/api/paper-trading",
        "/api/journal",
        "/api/backtests",
        "/api/strategies",
        "/api/ai/chat",
        "/api/ai/analyze",
        "/api/system/status",
        "/health",
    ):
        assert path in spec["paths"], path


def test_cors_origins_accept_comma_separated_and_json(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("CORS_ORIGINS", "http://a.test:3000, http://b.test:3000")
    assert Settings(_env_file=None).cors_origins == ["http://a.test:3000", "http://b.test:3000"]
    monkeypatch.setenv("CORS_ORIGINS", '["http://c.test"]')
    assert Settings(_env_file=None).cors_origins == ["http://c.test"]


def test_daily_ai_cap_pauses_every_ai_entry_point(client, monkeypatch):
    from app.services.ai_budget import budgeted_providers

    container = client.container

    class FakeProvider:
        name = "claude"

    monkeypatch.setattr(container, "ai_providers", lambda: [FakeProvider()])
    assert client.put("/api/settings/ai", json={"max_calls_per_day": 0}).status_code == 200
    providers, notes = client.portal.call(budgeted_providers, container)
    assert providers == [] and "cap reached" in notes[0]
    assert client.put("/api/settings/ai", json={"max_calls_per_day": 200}).status_code == 200
    providers, notes = client.portal.call(budgeted_providers, container)
    assert len(providers) == 1 and notes == []
