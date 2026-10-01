"""News provider abstraction.

* DemoNewsProvider: produces clearly-labelled DEMO items that only restate
  measurable facts from the DEMO market feed ("XAUUSD +1.2% over 24h in the
  demo feed"). It never invents real-world stories, sources or URLs.
* FinnhubNewsProvider: real headlines (NEWS_PROVIDER=finnhub, NEWS_API_KEY).
"""

from __future__ import annotations

import hashlib
import re
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import BaseModel, Field

from market_data.assets import AssetCatalog
from market_data.models import ProviderHealth
from market_data.providers.base import MarketDataError
from market_data.providers.demo import DemoMarketDataProvider

KEYWORDS: dict[str, list[str]] = {
    "XAUUSD": ["gold", "bullion", "xau", "precious metal"],
    "EURUSD": ["euro", "ecb", "eurozone", "lagarde", "eur/usd"],
    "GBPUSD": ["sterling", "pound", "bank of england", "boe", "gbp"],
    "USDJPY": ["yen", "boj", "bank of japan", "jpy"],
    "BTCUSD": ["bitcoin", "btc"],
    "ETHUSD": ["ether", "ethereum", "eth "],
    "NAS100": ["nasdaq", "tech stocks", "big tech"],
    "US30": ["dow jones", " dow "],
    "SPX500": ["s&p 500", "s&p", "wall street", "equities", "stocks"],
    "USOIL": ["oil", "crude", "opec", "wti", "brent"],
}
USD_WORDS = ["fed", "fomc", "powell", "dollar", "treasury", "inflation", "cpi", "payrolls", "jobs report"]
COUNTRY_WORDS = {
    "US": ["fed", "u.s.", "us ", "america", "wall street", "treasury"],
    "EU": ["ecb", "eurozone", "euro "],
    "GB": ["uk ", "britain", "bank of england"],
    "JP": ["japan", "boj"],
    "CN": ["china", "beijing"],
}


class NewsArticle(BaseModel):
    external_id: str
    headline: str
    summary: str | None = None
    source: str
    url: str | None = None
    published_at: datetime
    symbols: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    importance: str = "MEDIUM"
    provider: str
    is_demo: bool
    data_change_pct: float | None = None


def relevance(text: str) -> tuple[list[str], list[str]]:
    t = f" {text.lower()} "
    syms = [s for s, words in KEYWORDS.items() if any(w in t for w in words)]
    countries = [c for c, words in COUNTRY_WORDS.items() if any(w in t for w in words)]
    if any(w in t for w in USD_WORDS) and "US" not in countries:
        countries.append("US")
    return syms, countries


class NewsProvider(ABC):
    name = "abstract"
    is_demo = False

    @abstractmethod
    async def fetch(self, limit: int = 50) -> list[NewsArticle]: ...

    @abstractmethod
    async def validate(self) -> ProviderHealth: ...


class DemoNewsProvider(NewsProvider):
    name = "demo-news"
    is_demo = True
    SOURCE = "NEXUS Demo Feed (synthetic)"

    def __init__(self, market: DemoMarketDataProvider, catalog: AssetCatalog):
        self.market = market
        self.catalog = catalog

    async def fetch(self, limit: int = 50) -> list[NewsArticle]:
        from market_data.models import Timeframe

        now = self.market.now()
        hour = now.replace(minute=0, second=0, microsecond=0)
        out: list[NewsArticle] = []
        for h in range(0, 12, 3):
            stamp = hour - timedelta(hours=h)
            for spec in self.catalog.all():
                q = self.market.quote_sync(spec.symbol, at=stamp)
                chg = q.change_pct_24h or 0.0
                daily = spec.demo_daily_vol * 100
                if abs(chg) < 0.6 * daily:
                    continue
                direction = "up" if chg > 0 else "down"
                imp = "HIGH" if abs(chg) >= 1.6 * daily else "MEDIUM"
                hid = hashlib.sha256(f"{spec.symbol}|{stamp.isoformat()}|move".encode()).hexdigest()[:16]
                out.append(
                    NewsArticle(
                        external_id=hid,
                        headline=f"[DEMO] {spec.symbol} {direction} {chg:+.2f}% over 24h in the demo feed (at {q.price})",
                        summary=(
                            "Synthetic DEMO item generated from the demo price feed. It restates a measured demo price "
                            "move and is not real market news."
                        ),
                        source=self.SOURCE,
                        url=None,
                        published_at=stamp,
                        symbols=[spec.symbol],
                        countries=[],
                        importance=imp,
                        provider=self.name,
                        is_demo=True,
                        data_change_pct=round(chg, 3),
                    )
                )
            if h == 0:
                for spec in self.catalog.all():
                    s = self.market.candles_sync(spec.symbol, Timeframe.H1, 60)
                    df = s.closed_bars()
                    if len(df) < 25:
                        continue
                    rng = (df["high"].iloc[-1] - df["low"].iloc[-1]) / max(
                        (df["high"] - df["low"]).iloc[-21:-1].mean(), 1e-12
                    )
                    if rng >= 2.0:
                        hid = hashlib.sha256(f"{spec.symbol}|{stamp.isoformat()}|range".encode()).hexdigest()[
                            :16
                        ]
                        out.append(
                            NewsArticle(
                                external_id=hid,
                                headline=f"[DEMO] {spec.symbol} 1H bar range {rng:.1f}x its 20-bar average in the demo feed",
                                summary="Synthetic DEMO item derived from demo candles; not real market news.",
                                source=self.SOURCE,
                                url=None,
                                published_at=stamp,
                                symbols=[spec.symbol],
                                importance="MEDIUM",
                                provider=self.name,
                                is_demo=True,
                                data_change_pct=round(
                                    float((df["close"].iloc[-1] / df["open"].iloc[-1] - 1) * 100), 3
                                ),
                            )
                        )
        out.sort(key=lambda a: a.published_at, reverse=True)
        return out[:limit]

    async def validate(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name, status="DEMO", is_demo=True, detail="Synthetic items derived from demo prices"
        )


class FinnhubNewsProvider(NewsProvider):
    name = "finnhub"
    is_demo = False
    URL = "https://finnhub.io/api/v1/news"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def _category(self, category: str) -> list[dict]:
        try:
            r = await self._client.get(self.URL, params={"category": category, "token": self._key})
        except httpx.HTTPError as exc:
            raise MarketDataError(
                "DATA_PROVIDER_UNAVAILABLE", f"Finnhub request failed: {type(exc).__name__}"
            ) from exc
        if r.status_code != 200:
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", f"Finnhub HTTP {r.status_code}")
        data = r.json()
        return data if isinstance(data, list) else []

    async def fetch(self, limit: int = 50) -> list[NewsArticle]:
        items: list[NewsArticle] = []
        seen: set[str] = set()
        for cat in ("general", "forex", "crypto"):
            for raw in await self._category(cat):
                headline = str(raw.get("headline") or "").strip()
                url = raw.get("url")
                if not headline or not isinstance(url, str) or not re.match(r"^https?://", url):
                    continue
                ext = str(raw.get("id") or hashlib.sha256(url.encode()).hexdigest()[:20])
                if ext in seen:
                    continue
                seen.add(ext)
                summary = str(raw.get("summary") or "")[:2000] or None
                syms, countries = relevance(f"{headline} {summary or ''}")
                ts = raw.get("datetime")
                published = datetime.fromtimestamp(int(ts), UTC) if ts else datetime.now(UTC)
                items.append(
                    NewsArticle(
                        external_id=ext,
                        headline=headline[:500],
                        summary=summary,
                        source=str(raw.get("source") or "Finnhub")[:120],
                        url=url[:1000],
                        published_at=published,
                        symbols=syms,
                        countries=countries,
                        importance="HIGH" if len(syms) > 1 or "US" in countries else "MEDIUM",
                        provider=self.name,
                        is_demo=False,
                    )
                )
        items.sort(key=lambda a: a.published_at, reverse=True)
        return items[:limit]

    async def validate(self) -> ProviderHealth:
        started = time.perf_counter()
        try:
            await self._category("general")
        except MarketDataError as exc:
            return ProviderHealth(provider=self.name, status="ERROR", is_demo=False, detail=exc.message)
        return ProviderHealth(
            provider=self.name,
            status="CONNECTED",
            is_demo=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
