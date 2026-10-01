"""Economic calendar provider abstraction.

* DemoEconomicProvider: a deterministic, clearly-labelled SYNTHETIC schedule
  ("[DEMO] ..." names, source "NEXUS Demo Calendar (synthetic)") so the
  calendar UI and news-risk filters can be exercised offline. Values are
  synthetic and must never be read as real releases.
* FMPCalendarProvider: real events from Financial Modeling Prep
  (ECONOMIC_CALENDAR_PROVIDER=fmp, ECONOMIC_CALENDAR_API_KEY).
"""

from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
from pydantic import BaseModel

from market_data.models import ProviderHealth
from market_data.providers.base import MarketDataError

COUNTRY_CCY = {
    "US": "USD",
    "EU": "EUR",
    "EMU": "EUR",
    "DE": "EUR",
    "FR": "EUR",
    "IT": "EUR",
    "GB": "GBP",
    "UK": "GBP",
    "JP": "JPY",
    "CN": "CNY",
    "CA": "CAD",
    "AU": "AUD",
    "NZ": "NZD",
    "CH": "CHF",
}


class CalendarEvent(BaseModel):
    external_id: str
    event: str
    currency: str
    country: str
    scheduled_at: datetime
    impact: str  # LOW | MEDIUM | HIGH
    previous: str | None = None
    forecast: str | None = None
    actual: str | None = None
    source: str
    provider: str
    is_demo: bool


class EconomicCalendarProvider(ABC):
    name = "abstract"
    is_demo = False

    @abstractmethod
    async def fetch(self, start: datetime, end: datetime) -> list[CalendarEvent]: ...

    @abstractmethod
    async def validate(self) -> ProviderHealth: ...


# (weekday, hour, minute, name, currency, country, impact, base value, unit, cadence)
# cadence: "weekly" | "monthly-first" | "every-6-weeks" | "monthly-mid"
_DEMO_TEMPLATE = [
    (0, 14, 0, "ISM-style Manufacturing PMI", "USD", "United States", "MEDIUM", 50.0, "", "monthly-first"),
    (1, 9, 0, "Business Sentiment Index", "EUR", "Euro Area", "MEDIUM", 10.0, "", "weekly"),
    (1, 0, 30, "Household Spending y/y", "JPY", "Japan", "LOW", 1.0, "%", "weekly"),
    (1, 12, 30, "CPI m/m", "USD", "United States", "HIGH", 0.3, "%", "monthly-mid"),
    (2, 6, 0, "CPI y/y", "GBP", "United Kingdom", "HIGH", 2.5, "%", "monthly-mid"),
    (2, 14, 30, "Crude Oil Inventories", "USD", "United States", "MEDIUM", -1.2, "M", "weekly"),
    (2, 18, 0, "Central Bank Rate Decision", "USD", "United States", "HIGH", 4.5, "%", "every-6-weeks"),
    (3, 12, 30, "Initial Jobless Claims", "USD", "United States", "MEDIUM", 220.0, "K", "weekly"),
    (3, 12, 15, "Central Bank Rate Decision", "EUR", "Euro Area", "HIGH", 3.0, "%", "every-6-weeks"),
    (3, 14, 0, "Retail Sales m/m", "GBP", "United Kingdom", "MEDIUM", 0.2, "%", "weekly"),
    (4, 12, 30, "Non-Farm Payrolls", "USD", "United States", "HIGH", 180.0, "K", "monthly-first"),
    (4, 12, 30, "Unemployment Rate", "USD", "United States", "HIGH", 4.0, "%", "monthly-first"),
    (4, 23, 50, "Trade Balance", "JPY", "Japan", "LOW", -0.4, "T", "weekly"),
]
_DEMO_EPOCH = datetime(2022, 1, 3, tzinfo=UTC)


def _fmt(v: float | None, unit: str) -> str | None:
    return None if v is None else f"{v:.1f}{unit}"


class DemoEconomicProvider(EconomicCalendarProvider):
    name = "demo-calendar"
    is_demo = True
    SOURCE = "NEXUS Demo Calendar (synthetic)"

    def __init__(self, clock=None):  # type: ignore[no-untyped-def]
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def _occurs(cadence: str, day: datetime) -> bool:
        week = (day - _DEMO_EPOCH).days // 7
        if cadence == "weekly":
            return True
        if cadence == "monthly-first":
            return day.day <= 7
        if cadence == "monthly-mid":
            return 8 <= day.day <= 14
        if cadence == "every-6-weeks":
            return week % 6 == 2
        return False

    async def fetch(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        now = self._clock()
        out: list[CalendarEvent] = []
        day = start.replace(hour=0, minute=0, second=0, microsecond=0)
        while day <= end:
            for wd, hh, mm, name, ccy, country, impact, base, unit, cadence in _DEMO_TEMPLATE:
                if day.weekday() != wd or not self._occurs(cadence, day):
                    continue
                at = day.replace(hour=hh, minute=mm)
                if not start <= at <= end:
                    continue
                key = f"{name}|{ccy}|{at.isoformat()}"
                seed = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)
                rng = np.random.default_rng(seed)
                scale = abs(base) * 0.08 + 0.1
                prev = base + float(rng.normal(0, scale))
                fc = prev + float(rng.normal(0, scale * 0.5))
                act = fc + float(rng.normal(0, scale)) if at <= now else None
                out.append(
                    CalendarEvent(
                        external_id=hashlib.sha256(key.encode()).hexdigest()[:20],
                        event=f"[DEMO] {name}",
                        currency=ccy,
                        country=country,
                        scheduled_at=at,
                        impact=impact,
                        previous=_fmt(prev, unit),
                        forecast=_fmt(fc, unit),
                        actual=_fmt(act, unit),
                        source=self.SOURCE,
                        provider=self.name,
                        is_demo=True,
                    )
                )
            day += timedelta(days=1)
        out.sort(key=lambda e: e.scheduled_at)
        return out

    async def validate(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="DEMO",
            is_demo=True,
            detail="Synthetic schedule; not real economic events",
        )


class FMPCalendarProvider(EconomicCalendarProvider):
    name = "fmp"
    is_demo = False
    URL = "https://financialmodelingprep.com/stable/economic-calendar"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None):
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=15.0)

    async def fetch(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        params = {"from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d"), "apikey": self._key}
        try:
            r = await self._client.get(self.URL, params=params)
        except httpx.HTTPError as exc:
            raise MarketDataError(
                "DATA_PROVIDER_UNAVAILABLE", f"FMP request failed: {type(exc).__name__}"
            ) from exc
        if r.status_code != 200:
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", f"FMP HTTP {r.status_code}")
        data = r.json()
        if not isinstance(data, list):
            raise MarketDataError("DATA_PROVIDER_UNAVAILABLE", "FMP returned an unexpected payload")
        out: list[CalendarEvent] = []
        for raw in data:
            try:
                at = datetime.strptime(str(raw["date"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            except (KeyError, ValueError):
                continue
            country = str(raw.get("country") or "")
            ccy = str(raw.get("currency") or COUNTRY_CCY.get(country.upper(), country.upper()[:3]))
            impact = str(raw.get("impact") or "Low").upper()
            impact = impact if impact in ("LOW", "MEDIUM", "HIGH") else "LOW"

            def s(v: object) -> str | None:
                return None if v is None or v == "" else str(v)

            name = str(raw.get("event") or "").strip()
            if not name:
                continue
            out.append(
                CalendarEvent(
                    external_id=hashlib.sha256(f"{name}|{country}|{at.isoformat()}".encode()).hexdigest()[
                        :20
                    ],
                    event=name[:200],
                    currency=ccy,
                    country=country,
                    scheduled_at=at,
                    impact=impact,
                    previous=s(raw.get("previous")),
                    forecast=s(raw.get("estimate")),
                    actual=s(raw.get("actual")),
                    source="Financial Modeling Prep",
                    provider=self.name,
                    is_demo=False,
                )
            )
        return sorted(out, key=lambda e: e.scheduled_at)

    async def validate(self) -> ProviderHealth:
        started = time.perf_counter()
        now = datetime.now(UTC)
        try:
            await self.fetch(now, now + timedelta(days=1))
        except MarketDataError as exc:
            return ProviderHealth(provider=self.name, status="ERROR", is_demo=False, detail=exc.message)
        return ProviderHealth(
            provider=self.name,
            status="CONNECTED",
            is_demo=False,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
