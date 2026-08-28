"""Turn billed Jarvis periods into cumulative hourly points for HA statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .client import PeriodReading


@dataclass(frozen=True)
class CumulativePoint:
    start: datetime
    cumulative: float


def cumulative_points(
    periods: tuple[PeriodReading, ...] | list[PeriodReading],
) -> list[CumulativePoint]:
    ordered = sorted(periods, key=lambda item: item.start)
    total = 0.0
    points: list[CumulativePoint] = []
    for item in ordered:
        total += item.amount
        hour = item.start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        if points and points[-1].start == hour:
            points[-1] = CumulativePoint(start=hour, cumulative=total)
        else:
            points.append(CumulativePoint(start=hour, cumulative=total))
    return points
