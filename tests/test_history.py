"""Billed periods become cumulative hourly points for Energy statistics."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from custom_components.sp_group.client import SG_TZ, PeriodReading, SpGroupClient
from custom_components.sp_group.history import (
    cumulative_points,
    fold_half_hours,
    merge_ami_periods,
)
from custom_components.sp_group.mapper import electricity_graph_periods

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


def test_fold_half_hours_sums_clock_hour() -> None:
    start = datetime(2026, 8, 2, 0, 0, tzinfo=SG_TZ)
    folded = fold_half_hours(
        (
            PeriodReading(start=start, amount=0.4),
            PeriodReading(start=start.replace(minute=30), amount=0.6),
        )
    )
    assert len(folded) == 1
    assert folded[0].amount == pytest.approx(1.0)
    assert folded[0].start.minute == 0


def test_merge_prefers_hourly_on_same_day() -> None:
    day = datetime(2026, 8, 2, 0, 0, tzinfo=SG_TZ)
    daily = (PeriodReading(start=day, amount=99.0),)
    hourly = (
        PeriodReading(start=day, amount=1.0),
        PeriodReading(start=day.replace(hour=1), amount=2.0),
    )
    merged = merge_ami_periods(daily, hourly)
    assert len(merged) == 2
    assert all(item.amount != 99.0 for item in merged)


def test_electricity_graph_uses_ami_not_billed() -> None:
    client = SpGroupClient("user@example.com", "secret", transport=FixtureTransport())
    usage = client.fetch_usage()
    graph = electricity_graph_periods(usage)
    assert sum(item.amount for item in graph) == pytest.approx(24.0)
    points = cumulative_points(graph)
    assert points[-1].cumulative == pytest.approx(24.0)
