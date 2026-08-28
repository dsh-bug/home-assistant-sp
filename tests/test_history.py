"""Billed periods become cumulative hourly points for Energy statistics."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from custom_components.sp_group.client import PeriodReading, SpGroupClient
from custom_components.sp_group.history import cumulative_points

from .conftest import FixtureTransport, billed_totals_from_charts_payload, load_fixture


def test_cumulative_points_sum_fixture_currents() -> None:
    charts = json.loads(load_fixture("jarvis_charts.json"))
    expected_kwh, expected_m3 = billed_totals_from_charts_payload(charts)
    client = SpGroupClient("user@example.com", "secret", transport=FixtureTransport())
    usage = client.fetch_usage()
    elec = cumulative_points(usage.electricity_periods)
    water = cumulative_points(usage.water_periods)
    assert elec[-1].cumulative == expected_kwh
    assert water[-1].cumulative == expected_m3
    assert elec[0].start.tzinfo is not None
    assert elec[0].start == elec[0].start.replace(minute=0, second=0, microsecond=0)


def test_same_hour_periods_collapse() -> None:
    start = datetime(2026, 6, 1, 0, 15, tzinfo=UTC)
    points = cumulative_points(
        (
            PeriodReading(start=start, amount=10.0),
            PeriodReading(start=start.replace(minute=45), amount=2.5),
        )
    )
    assert len(points) == 1
    assert points[0].cumulative == 12.5
    assert points[0].start.minute == 0
