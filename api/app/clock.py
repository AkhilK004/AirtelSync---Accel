"""Demo clock: the dataset's "today" (settings.TODAY) with the real time of day. One source of time for orders, ETAs and events."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.config import settings


def today() -> date:
    return date.fromisoformat(settings.TODAY)


def now() -> datetime:
    t = datetime.now(timezone.utc)
    d = today()
    return t.replace(year=d.year, month=d.month, day=d.day)


def now_iso() -> str:
    return now().isoformat(timespec="seconds")
