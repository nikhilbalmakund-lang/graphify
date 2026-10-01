from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pandas as pd
import pytest

from market_data.assets import DEFAULT_CATALOG, AssetCatalog
from market_data.cache.candle_cache import CandleCache
from market_data.models import CandleSeries, SessionType, Timeframe
from market_data.normalization.validation import IssueSeverity, validate_ohlcv_frame, validate_series
from market_data.providers.base import MarketDataError
from market_data.providers.demo import DemoMarketDataProvider
from market_data.providers.twelvedata import TwelveDataProvider
from market_data.sessions import is_open

NOW = datetime(2026, 10, 1, 14, 30, 27, tzinfo=UTC)  # Thursday


def demo(now=NOW):
    return DemoMarketDataProvider(clock=lambda: now)


def test_demo_prices_are_deterministic_across_instances():
    a, b = demo(), demo()
    for sym in DEFAULT_CATALOG.symbols():
        assert a.quote_sync(sym).price == b.quote_sync(sym).price
        assert a.quote_sync(sym).is_demo is True
        assert a.quote_sync(sym).provider == "demo"


def test_timeframes_are_consistent():
    p = demo()
    h1 = p.candles_sync("XAUUSD", Timeframe.H1, 48).df
    h4 = p.candles_sync("XAUUSD", Timeframe.H4, 12).df
    d1 = p.candles_sync("XAUUSD", Timeframe.D1, 3).df
    # Last close of every timeframe equals the live demo price.
    price = p.model("XAUUSD").price_at(NOW)
    tol = 10 ** -(DEFAULT_CATALOG.get("XAUUSD").price_precision + 2)
    assert h1["close"].iloc[-1] == pytest.approx(price, abs=tol)
    assert h4["close"].iloc[-1] == pytest.approx(price, abs=tol)
    assert d1["close"].iloc[-1] == pytest.approx(price, abs=tol)
    # A complete 4H bar equals the aggregate of its four 1H bars.
    bar = h4.index[-2]
    hours = h1[(h1.index >= bar) & (h1.index < bar + pd.Timedelta(hours=4))]
    assert len(hours) == 4
    assert h4.loc[bar, "open"] == pytest.approx(hours["open"].iloc[0])
    assert h4.loc[bar, "high"] == pytest.approx(hours["high"].max())
    assert h4.loc[bar, "low"] == pytest.approx(hours["low"].min())
    assert h4.loc[bar, "close"] == pytest.approx(hours["close"].iloc[-1])


def test_candles_never_extend_past_now():
    p = demo()
    for tf in [Timeframe.M1, Timeframe.M15, Timeframe.H1, Timeframe.D1]:
        s = p.candles_sync("EURUSD", tf, 100)
        assert s.df.index[-1] <= pd.Timestamp(NOW)
        assert s.last_bar_complete is False


def test_ohlc_relationships_hold():
    s = demo().candles_sync("BTCUSD", Timeframe.M15, 500).df
    assert (s["high"] >= s[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (s["low"] <= s[["open", "close"]].min(axis=1) + 1e-9).all()
    assert (s["volume"] >= 0).all()


def test_weekend_handling_for_fx_and_crypto():
    saturday = datetime(2026, 10, 3, 12, 0, 30, tzinfo=UTC)
    p = demo(saturday)
    fx = p.candles_sync("EURUSD", Timeframe.H1, 5).df
    assert fx.index[-1] < pd.Timestamp(datetime(2026, 10, 2, 21, 0, tzinfo=UTC))
    assert p.quote_sync("EURUSD").market_open is False
    btc = p.candles_sync("BTCUSD", Timeframe.H1, 5).df
    assert btc.index[-1] == pd.Timestamp(datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
    assert p.quote_sync("BTCUSD").market_open is True


def test_session_rules():
    assert is_open(SessionType.FX, datetime(2026, 10, 2, 20, 59, tzinfo=UTC))[0]
    assert not is_open(SessionType.FX, datetime(2026, 10, 2, 21, 0, tzinfo=UTC))[0]
    assert not is_open(SessionType.FX, datetime(2026, 10, 4, 20, 59, tzinfo=UTC))[0]
    assert is_open(SessionType.FX, datetime(2026, 10, 4, 21, 0, tzinfo=UTC))[0]
    assert not is_open(SessionType.CFD, datetime(2026, 9, 30, 21, 30, tzinfo=UTC))[0]
    assert is_open(SessionType.CRYPTO, datetime(2026, 10, 3, 3, 0, tzinfo=UTC))[0]


def test_range_request_and_too_large_range():
    p = demo()
    s = p.candles_sync("XAUUSD", Timeframe.H1, start=NOW - timedelta(days=10), end=NOW - timedelta(days=5))
    assert s.df.index[0] >= pd.Timestamp(NOW - timedelta(days=10))
    assert s.df.index[-1] < pd.Timestamp(NOW - timedelta(days=5))
    with pytest.raises(MarketDataError):
        p.candles_sync("XAUUSD", Timeframe.M1, start=NOW - timedelta(days=400), end=NOW)


def _series(df, tf=Timeframe.H1, symbol="BTCUSD"):
    return CandleSeries(symbol=symbol, timeframe=tf, provider="test", is_demo=True, df=df)


def test_validation_clean_demo_series_is_usable():
    s = demo().candles_sync("XAUUSD", Timeframe.M15, 300)
    clean, report = validate_series(s, DEFAULT_CATALOG.get("XAUUSD"), NOW)
    assert report.usable
    assert not report.is_stale
    assert report.missing_bars == 0
    assert report.quality_score == 1.0


def test_validation_detects_duplicates_invalid_ohlc_and_negative_volume():
    s = demo().candles_sync("BTCUSD", Timeframe.H1, 200)
    df = s.df.copy()
    df = pd.concat([df, df.iloc[[50]]]).sort_index()  # duplicate
    df.iloc[10, df.columns.get_loc("high")] = df.iloc[10]["low"] - 1  # invalid OHLC
    df.iloc[20, df.columns.get_loc("volume")] = -5  # negative volume
    clean, report = validate_series(_series(df), DEFAULT_CATALOG.get("BTCUSD"), NOW)
    codes = {i.code for i in report.issues}
    assert {"DUPLICATE_CANDLES", "INVALID_OHLC", "NEGATIVE_VOLUME"} <= codes
    assert report.duplicate_bars == 1
    assert len(clean.df) == 198
    assert not clean.df.index.duplicated().any()


def test_validation_rejects_series_with_many_invalid_rows():
    df = demo().candles_sync("BTCUSD", Timeframe.H1, 200).df.copy()
    df.iloc[:10, df.columns.get_loc("close")] = -1
    _, report = validate_series(_series(df), DEFAULT_CATALOG.get("BTCUSD"), NOW)
    assert not report.usable
    assert "INVALID_MARKET_DATA" in report.critical_codes


def test_validation_detects_stale_and_missing():
    df = demo().candles_sync("BTCUSD", Timeframe.H1, 200).df.copy()
    stale_now = NOW + timedelta(hours=5)
    _, report = validate_series(_series(df), DEFAULT_CATALOG.get("BTCUSD"), stale_now)
    assert report.is_stale and not report.usable
    holes = df.drop(df.index[50:120])
    _, report2 = validate_series(_series(holes), DEFAULT_CATALOG.get("BTCUSD"), NOW)
    assert report2.missing_bars == 70
    assert any(i.code == "MISSING_CANDLES" and i.severity == IssueSeverity.CRITICAL for i in report2.issues)


def test_validation_empty_series():
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"], index=pd.DatetimeIndex([], tz="UTC"))
    _, report = validate_series(_series(empty), DEFAULT_CATALOG.get("BTCUSD"), NOW)
    assert not report.usable


def test_validate_ohlcv_frame_for_imports():
    idx = pd.date_range("2024-01-01", periods=3, freq="1h", tz="UTC")
    ok = pd.DataFrame({"open": [1.0, 2.0, 3.0], "high": [2.0, 3.0, 4.0], "low": [0.5, 1.5, 2.5],
                       "close": [1.5, 2.5, 3.5], "volume": [1.0, 1.0, 1.0]}, index=idx)
    assert validate_ohlcv_frame(ok) == []
    bad = ok.copy()
    bad.loc[idx[1], "high"] = 0.1
    bad.loc[idx[2], "volume"] = -1
    errors = validate_ohlcv_frame(bad)
    assert any("OHLC" in e for e in errors) and any("negative volume" in e for e in errors)


def _td_transport(handler):
    return httpx.AsyncClient(base_url="https://api.twelvedata.com", transport=httpx.MockTransport(handler))


async def test_twelvedata_parses_quotes_and_candles():
    def handler(request: httpx.Request):
        assert request.url.params["apikey"] == "k"
        if request.url.path == "/quote":
            return httpx.Response(200, json={"symbol": "EUR/USD", "close": "1.10000", "previous_close": "1.09000",
                                             "timestamp": 1790000000, "is_market_open": True})
        values = [{"datetime": f"2026-10-01 {h:02d}:00:00", "open": "1.1", "high": "1.2", "low": "1.0", "close": "1.15"} for h in range(5)]
        return httpx.Response(200, json={"status": "ok", "values": values})

    p = TwelveDataProvider("k", client=_td_transport(handler), clock=lambda: NOW)
    q = await p.get_quote("EURUSD")
    assert q.price == 1.1 and q.is_demo is False and q.provider == "twelvedata" and q.spread_is_estimate
    assert q.change_pct_24h == pytest.approx(0.917, abs=1e-3)
    s = await p.get_candles("EURUSD", Timeframe.H1, 5)
    assert len(s.df) == 5 and s.volume_available is False and not s.is_demo
    health = await p.validate()
    assert health.status == "CONNECTED"


async def test_twelvedata_errors_are_reported_not_hidden():
    def handler(request):
        return httpx.Response(200, json={"status": "error", "code": 401, "message": "Invalid API key"})

    p = TwelveDataProvider("bad", client=_td_transport(handler), clock=lambda: NOW)
    with pytest.raises(MarketDataError) as exc:
        await p.get_quote("EURUSD")
    assert exc.value.code == "DATA_PROVIDER_UNAVAILABLE"
    health = await p.validate()
    assert health.status == "ERROR" and "Invalid API key" in health.detail


async def test_candle_cache_hits_and_incremental_merge():
    p = demo()
    calls = []

    async def fetch(n):
        calls.append(n)
        return p.candles_sync("XAUUSD", Timeframe.H1, n)

    cache = CandleCache(ttl_multiplier=0.0)
    first = await cache.get("demo", "XAUUSD", Timeframe.H1, 100, fetch)
    second = await cache.get("demo", "XAUUSD", Timeframe.H1, 100, fetch)
    assert calls[0] == 100 and calls[1] < 10  # incremental refresh fetched only recent bars
    assert len(second.df) == 100
    assert np.allclose(first.df["close"].to_numpy(), second.df["close"].to_numpy())


def test_catalog_aliases_and_overrides():
    assert DEFAULT_CATALOG.resolve("gold") == "XAUUSD"
    assert DEFAULT_CATALOG.resolve("eur/usd") == "EURUSD"
    assert DEFAULT_CATALOG.resolve("nonsense") is None
    cat = AssetCatalog(symbol_overrides={"twelvedata": {"NAS100": "QQQ"}})
    assert cat.get("NAS100").provider_symbols["twelvedata"] == "QQQ"
