"""Simulated clock for the twin. Replay is deterministic from (seed, clock)."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")  # synthetic stores sit in Central time


class SimClock:
    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("SimClock needs a timezone-aware start")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> datetime:
        if delta < timedelta(0):
            raise ValueError("the clock never runs backwards")
        self._now = self._now + delta
        return self._now

    def set(self, when: datetime) -> datetime:
        if when < self._now:
            raise ValueError("the clock never runs backwards")
        self._now = when
        return self._now


def at(y: int, mo: int, d: int, h: int = 0, mi: int = 0) -> datetime:
    return datetime(y, mo, d, h, mi, tzinfo=TZ)
