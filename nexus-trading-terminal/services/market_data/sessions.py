"""Trading-session rules (UTC approximations).

These are deliberately simple, documented approximations of retail broker
hours. They ignore DST shifts and exchange holidays:

* FX:     open Sunday 21:00 UTC -> Friday 21:00 UTC
* CFD:    FX hours plus a daily 21:00-22:00 UTC break Monday-Thursday
          (metals, energy and index CFDs)
* CRYPTO: 24/7
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from market_data.models import SessionType

WEEKLY_CLOSE_HOUR = 21


def is_open(session: SessionType, ts: datetime) -> tuple[bool, str]:
    ts = ts.astimezone(UTC)
    if session == SessionType.CRYPTO:
        return True, "Crypto trades 24/7"
    wd, hour = ts.weekday(), ts.hour
    if wd == 5 or (wd == 4 and hour >= WEEKLY_CLOSE_HOUR) or (wd == 6 and hour < WEEKLY_CLOSE_HOUR):
        return False, "Weekend close (Fri 21:00 - Sun 21:00 UTC)"
    if session == SessionType.CFD and wd <= 3 and hour == WEEKLY_CLOSE_HOUR:
        return False, "Daily maintenance break (21:00-22:00 UTC)"
    return True, "Regular session"


def open_mask(session: SessionType, index: pd.DatetimeIndex) -> np.ndarray:
    """Vectorised version of `is_open` for a UTC DatetimeIndex (minute stamps)."""
    if session == SessionType.CRYPTO:
        return np.ones(len(index), dtype=bool)
    wd = np.asarray(index.weekday)
    hour = np.asarray(index.hour)
    closed = (wd == 5) | ((wd == 4) & (hour >= WEEKLY_CLOSE_HOUR)) | ((wd == 6) & (hour < WEEKLY_CLOSE_HOUR))
    if session == SessionType.CFD:
        closed |= (wd <= 3) & (hour == WEEKLY_CLOSE_HOUR)
    return ~closed


def session_name(ts: datetime) -> str:
    """Name of the dominant global session for a UTC timestamp (for briefings)."""
    h = ts.astimezone(UTC).hour
    if 0 <= h < 7:
        return "ASIA"
    if 7 <= h < 12:
        return "LONDON"
    if 12 <= h < 16:
        return "LONDON_NY_OVERLAP"
    if 16 <= h < 21:
        return "NEW_YORK"
    return "POST_MARKET"
