"""Market data quality validation.

Every series that reaches the quant engine passes through `validate_series`,
which detects and (where safe) removes bad rows, and reports:

* missing candles            * duplicate candles      * stale data
* invalid OHLC relationships * negative volume        * timestamp problems
* non-positive prices        * NaN values             * isolated price spikes

Rows that are objectively invalid are rejected. If more than a small fraction
of a series is invalid, the whole series is marked unusable (CRITICAL) and the
signal engine will return NO_TRADE with INVALID_MARKET_DATA.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from market_data.models import OHLCV_COLUMNS, AssetSpec, CandleSeries, Timeframe
from market_data.sessions import is_open, open_mask

MAX_INVALID_FRACTION = 0.01
MISSING_WARN_FRACTION = 0.10
MISSING_CRITICAL_FRACTION = 0.30
SPIKE_MULTIPLE = 15.0


class IssueSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class DataIssue(BaseModel):
    code: str
    severity: IssueSeverity
    count: int = 0
    detail: str = ""


class DataQualityReport(BaseModel):
    symbol: str
    timeframe: str
    provider: str
    is_demo: bool
    bars: int
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    issues: list[DataIssue] = Field(default_factory=list)
    missing_bars: int = 0
    duplicate_bars: int = 0
    invalid_rows: int = 0
    negative_volume: int = 0
    last_bar_age_seconds: float | None = None
    is_stale: bool = False
    market_open: bool = True
    usable: bool = True
    quality_score: float = 1.0

    def add(self, code: str, severity: IssueSeverity, count: int = 0, detail: str = "") -> None:
        self.issues.append(DataIssue(code=code, severity=severity, count=count, detail=detail))
        if severity == IssueSeverity.CRITICAL:
            self.usable = False

    @property
    def critical_codes(self) -> list[str]:
        return [i.code for i in self.issues if i.severity == IssueSeverity.CRITICAL]


def stale_threshold(timeframe: Timeframe) -> timedelta:
    return timedelta(seconds=max(2 * timeframe.seconds, 180))


def _expected_bar_opens(
    first: pd.Timestamp, last: pd.Timestamp, timeframe: Timeframe, spec: AssetSpec
) -> pd.DatetimeIndex:
    grid = pd.date_range(first, last, freq=timeframe.pandas_rule)
    if len(grid) == 0:
        return grid
    end_minute = grid + pd.Timedelta(seconds=timeframe.seconds - 60)
    tradable = open_mask(spec.session, grid) | open_mask(spec.session, pd.DatetimeIndex(end_minute))
    return grid[tradable]


def validate_series(
    series: CandleSeries, spec: AssetSpec, now: datetime | None = None
) -> tuple[CandleSeries, DataQualityReport]:
    """Validate and clean a candle series. Returns (clean_series, report)."""
    now = (now or datetime.now(UTC)).astimezone(UTC)
    df = series.df.copy()
    report = DataQualityReport(
        symbol=series.symbol,
        timeframe=series.timeframe.value,
        provider=series.provider,
        is_demo=series.is_demo,
        bars=len(df),
        checked_at=now,
    )

    if df.empty:
        report.add("INSUFFICIENT_DATA", IssueSeverity.CRITICAL, 0, "No candles returned")
        report.quality_score = 0.0
        return series, report

    missing_cols = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing_cols:
        report.add(
            "INVALID_MARKET_DATA",
            IssueSeverity.CRITICAL,
            len(missing_cols),
            f"Missing columns {missing_cols}",
        )
        report.quality_score = 0.0
        return series, report

    if not isinstance(df.index, pd.DatetimeIndex) or df.index.tz is None:
        report.add(
            "TIMESTAMP_INVALID", IssueSeverity.CRITICAL, len(df), "Index must be a tz-aware DatetimeIndex"
        )
        report.quality_score = 0.0
        return series, report

    total = len(df)
    nat = df.index.isna()
    if nat.any():
        report.add(
            "TIMESTAMP_INVALID", IssueSeverity.WARNING, int(nat.sum()), "Rows without a timestamp removed"
        )
        df = df[~nat]

    if not df.index.is_monotonic_increasing:
        report.add(
            "TIMESTAMP_ORDER", IssueSeverity.WARNING, 0, "Candles were out of order and have been sorted"
        )
        df = df.sort_index()

    dup = df.index.duplicated(keep="last")
    if dup.any():
        report.duplicate_bars = int(dup.sum())
        report.add(
            "DUPLICATE_CANDLES",
            IssueSeverity.WARNING,
            report.duplicate_bars,
            "Duplicate timestamps removed (kept latest)",
        )
        df = df[~dup]

    future = df.index > pd.Timestamp(now + timedelta(seconds=series.timeframe.seconds))
    if future.any():
        report.add(
            "TIMESTAMP_FUTURE",
            IssueSeverity.CRITICAL if future.sum() > 1 else IssueSeverity.WARNING,
            int(future.sum()),
            "Candles timestamped in the future removed",
        )
        df = df[~future]

    o, h, low, c, v = (df[col].to_numpy(dtype="float64") for col in OHLCV_COLUMNS)
    nan_rows = np.isnan(o) | np.isnan(h) | np.isnan(low) | np.isnan(c)
    eps = 1e-9 * np.nanmax(np.abs(c)) if len(c) else 0.0
    with np.errstate(invalid="ignore"):
        bad_ohlc = (~nan_rows) & (
            (h + eps < np.maximum(o, c))
            | (low - eps > np.minimum(o, c))
            | (h + eps < low)
            | (o <= 0)
            | (h <= 0)
            | (low <= 0)
            | (c <= 0)
        )
        neg_vol = (~np.isnan(v)) & (v < 0)
    invalid = nan_rows | bad_ohlc | neg_vol
    if nan_rows.any():
        report.add(
            "MISSING_VALUES", IssueSeverity.WARNING, int(nan_rows.sum()), "Rows with NaN prices rejected"
        )
    if bad_ohlc.any():
        report.add(
            "INVALID_OHLC",
            IssueSeverity.WARNING,
            int(bad_ohlc.sum()),
            "Rows violating OHLC relationships rejected",
        )
    if neg_vol.any():
        report.negative_volume = int(neg_vol.sum())
        report.add(
            "NEGATIVE_VOLUME",
            IssueSeverity.WARNING,
            report.negative_volume,
            "Rows with negative volume rejected",
        )
    report.invalid_rows = int(invalid.sum())
    if total and report.invalid_rows / total > MAX_INVALID_FRACTION:
        report.add(
            "INVALID_MARKET_DATA",
            IssueSeverity.CRITICAL,
            report.invalid_rows,
            f"{report.invalid_rows}/{total} rows invalid (> {MAX_INVALID_FRACTION:.0%}); series rejected",
        )
    df = df[~invalid]

    if len(df) >= 3:
        logret = np.abs(np.diff(np.log(df["close"].to_numpy())))
        med = float(np.median(logret[logret > 0])) if (logret > 0).any() else 0.0
        if med > 0:
            spikes = int((logret > SPIKE_MULTIPLE * med * 4).sum())
            if spikes:
                report.add(
                    "PRICE_SPIKE", IssueSeverity.WARNING, spikes, "Unusually large bar-to-bar moves detected"
                )

    if len(df) >= 2 and series.timeframe != Timeframe.W1:
        expected = _expected_bar_opens(df.index[0], df.index[-1], series.timeframe, spec)
        if series.timeframe == Timeframe.D1:
            missing = 0
            gaps = np.diff(df.index.asi8) / 1e9 / 86_400
            limit = 1.5 if spec.session.value == "CRYPTO" else 4.0
            missing = int((gaps > limit).sum())
        else:
            missing = len(expected.difference(df.index))
        report.missing_bars = missing
        frac = missing / max(len(expected), 1)
        if missing:
            sev = IssueSeverity.INFO
            if frac > MISSING_CRITICAL_FRACTION:
                sev = IssueSeverity.CRITICAL
            elif frac > MISSING_WARN_FRACTION:
                sev = IssueSeverity.WARNING
            report.add("MISSING_CANDLES", sev, missing, f"{missing} expected bars absent ({frac:.1%})")

    market_open, reason = is_open(spec.session, now)
    report.market_open = market_open
    if len(df):
        last_open = df.index[-1].to_pydatetime()
        last_close_time = last_open + timedelta(seconds=series.timeframe.seconds)
        age = (now - min(last_close_time, now)).total_seconds()
        report.last_bar_age_seconds = round(age, 1)
        if market_open and now - last_close_time > stale_threshold(series.timeframe):
            report.is_stale = True
            report.add(
                "STALE_MARKET_DATA",
                IssueSeverity.CRITICAL,
                0,
                f"Last bar closed {int(age)}s ago while market is open",
            )
        elif not market_open:
            report.add("MARKET_CLOSED", IssueSeverity.INFO, 0, reason)

    report.bars = len(df)
    penalty = 0.0
    for issue in report.issues:
        penalty += {IssueSeverity.INFO: 0.0, IssueSeverity.WARNING: 0.08, IssueSeverity.CRITICAL: 0.5}[
            issue.severity
        ]
    report.quality_score = round(max(0.0, 1.0 - penalty), 3)

    clean = CandleSeries(
        symbol=series.symbol,
        timeframe=series.timeframe,
        provider=series.provider,
        is_demo=series.is_demo,
        df=df,
        fetched_at=series.fetched_at,
        last_bar_complete=series.last_bar_complete,
        volume_available=series.volume_available,
    )
    return clean, report


def validate_ohlcv_frame(df: pd.DataFrame) -> list[str]:
    """Strict validation for user-imported CSV data. Returns a list of errors (empty == valid)."""
    errors: list[str] = []
    for col in OHLCV_COLUMNS:
        if col not in df.columns:
            errors.append(f"missing column '{col}'")
    if errors:
        return errors
    if df.index.isna().any():
        errors.append(f"{int(df.index.isna().sum())} rows have unparseable timestamps")
    if df.index.duplicated().any():
        errors.append(f"{int(df.index.duplicated().sum())} duplicate timestamps")
    if not df.index.is_monotonic_increasing:
        errors.append("timestamps are not in ascending order")
    vals = df[OHLCV_COLUMNS]
    if vals.isna().any().any():
        errors.append(f"{int(vals.isna().any(axis=1).sum())} rows contain empty/non-numeric values")
    o, h, low, c, v = (df[col] for col in OHLCV_COLUMNS)
    if ((o <= 0) | (h <= 0) | (low <= 0) | (c <= 0)).any():
        errors.append("non-positive prices present")
    if ((h < o.combine(c, max)) | (low > o.combine(c, min)) | (h < low)).any():
        errors.append("rows violate OHLC relationships (high/low outside open/close)")
    if (v < 0).any():
        errors.append("negative volume present")
    return errors
