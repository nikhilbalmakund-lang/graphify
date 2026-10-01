"""Normalisation helpers: turn heterogeneous provider/CSV records into the
canonical OHLCV frame (UTC DatetimeIndex, float columns, ascending order)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np
import pandas as pd

from market_data.models import OHLCV_COLUMNS


def frame_from_records(records: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(list(records))
    if df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([], tz="UTC"))
    ts = parse_timestamps(df["timestamp"])
    out = pd.DataFrame(index=pd.DatetimeIndex(ts, name=None))
    for col in OHLCV_COLUMNS:
        out[col] = pd.to_numeric(df[col], errors="coerce").to_numpy() if col in df else np.nan
    return out.sort_index()


def parse_timestamps(values: pd.Series) -> pd.DatetimeIndex:
    """Parse ISO strings or epoch seconds/milliseconds into a UTC DatetimeIndex."""
    if pd.api.types.is_numeric_dtype(values):
        arr = values.astype("float64")
        unit = "ms" if arr.abs().max() > 1e11 else "s"
        return pd.DatetimeIndex(pd.to_datetime(arr, unit=unit, utc=True))
    parsed = pd.to_datetime(values, utc=True, errors="coerce", format="mixed")
    return pd.DatetimeIndex(parsed)


def ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing OHLCV columns: {missing}")
    return df[OHLCV_COLUMNS].astype("float64")
