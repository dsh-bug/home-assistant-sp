"""HA sensor specs from parsed usage; failed auth yields none."""

from __future__ import annotations

import json

import pytest

from custom_components.sp_group.client import AuthError, SpGroupClient
from custom_components.sp_group.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_WATER,
    SENSOR_KEY_ELECTRICITY,
    SENSOR_KEY_WATER,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_M3,
)
from custom_components.sp_group.mapper import extra_attributes, sensors_from_usage

from .conftest import FixtureTransport, billed_totals_from_charts_payload, load_fixture


def test_sensors_match_energy_dashboard_contract() -> None:
    charts = json.loads(load_fixture("jarvis_charts.json"))
    expected_kwh, expected_m3 = billed_totals_from_charts_payload(charts)
    client = SpGroupClient("user@example.com", "secret", transport=FixtureTransport())
    usage = client.fetch_usage()
    specs = sensors_from_usage(usage)
    by_key = {spec.key: spec for spec in specs}

    electricity = by_key["electricity"]
    assert electricity.native_value == expected_kwh
    assert electricity.device_class == DEVICE_CLASS_ENERGY
    assert electricity.state_class == STATE_CLASS_TOTAL_INCREASING
    assert electricity.unit_of_measurement == UNIT_KWH

    water = by_key["water"]
    assert water.native_value == expected_m3
    assert water.device_class == DEVICE_CLASS_WATER
    assert water.state_class == STATE_CLASS_TOTAL_INCREASING
    assert water.unit_of_measurement == UNIT_M3

    elec_attrs = extra_attributes(usage, SENSOR_KEY_ELECTRICITY)
    water_attrs = extra_attributes(usage, SENSOR_KEY_WATER)
    assert elec_attrs["premise_id"] == usage.premise_id
    assert elec_attrs["period_count"] == len(usage.electricity_periods)
    last_elec = max(usage.electricity_periods, key=lambda item: item.start)
    assert elec_attrs["last_period_amount"] == last_elec.amount
    assert water_attrs["period_count"] == len(usage.water_periods)


def test_failed_auth_does_not_yield_sensor_values() -> None:
    client = SpGroupClient(
        "user@example.com", "wrong", transport=FixtureTransport(fail_login=True)
    )
    with pytest.raises(AuthError):
        client.fetch_usage()
    assert sensors_from_usage(None) == []
