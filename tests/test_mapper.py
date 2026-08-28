"""HA sensor specs from parsed usage; failed auth yields none."""

from __future__ import annotations

import json

import pytest

from custom_components.sp_group.client import AuthError, SpGroupClient
from custom_components.sp_group.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_WATER,
    ENTITY_CATEGORY_DIAGNOSTIC,
    SENSOR_KEY_ACCOUNT,
    SENSOR_KEY_ELECTRICITY,
    SENSOR_KEY_ELECTRICITY_LAST,
    SENSOR_KEY_GAS,
    SENSOR_KEY_WATER,
    SENSOR_KEY_WATER_LAST,
    STATE_CLASS_MEASUREMENT,
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
    # AMI daily 10+12 plus two folded hours of 1.0 kWh each.
    assert electricity.native_value == pytest.approx(24.0)
    assert electricity.device_class == DEVICE_CLASS_ENERGY
    assert electricity.state_class == STATE_CLASS_TOTAL_INCREASING
    assert electricity.unit_of_measurement == UNIT_KWH
    assert expected_kwh > 0

    water = by_key["water"]
    assert water.native_value == expected_m3
    assert water.device_class == DEVICE_CLASS_WATER
    assert water.state_class == STATE_CLASS_TOTAL_INCREASING
    assert water.unit_of_measurement == UNIT_M3

    last_elec = by_key[SENSOR_KEY_ELECTRICITY_LAST]
    assert last_elec.state_class == STATE_CLASS_MEASUREMENT
    last_water = by_key[SENSOR_KEY_WATER_LAST]
    assert last_water.state_class == STATE_CLASS_MEASUREMENT

    account = by_key[SENSOR_KEY_ACCOUNT]
    assert account.native_value == "Active"
    assert account.entity_category == ENTITY_CATEGORY_DIAGNOSTIC
    assert SENSOR_KEY_GAS not in by_key

    elec_attrs = extra_attributes(usage, SENSOR_KEY_ELECTRICITY)
    water_attrs = extra_attributes(usage, SENSOR_KEY_WATER)
    assert elec_attrs["premise_id"] == usage.premise_id
    assert elec_attrs["account_number"] == "1234567890"
    assert elec_attrs["address"] == "1 Example Road, Singapore"
    assert elec_attrs["period_count"] == 4
    assert elec_attrs["ami_half_hour_count"] == 4
    assert elec_attrs["last_period_amount"] == pytest.approx(1.0)
    assert water_attrs["period_count"] == len(usage.water_periods)
    account_attrs = extra_attributes(usage, SENSOR_KEY_ACCOUNT)
    assert account_attrs["meter_reading_title"] == "Sep 2026"


def test_gas_only_charts_yield_gas_sensors() -> None:
    client = SpGroupClient(
        "user@example.com",
        "secret",
        transport=FixtureTransport(charts_fixture="jarvis_charts_gas.json"),
    )
    usage = client.fetch_usage()
    by_key = {spec.key: spec for spec in sensors_from_usage(usage)}
    assert SENSOR_KEY_ELECTRICITY not in by_key
    assert SENSOR_KEY_WATER not in by_key
    gas = by_key[SENSOR_KEY_GAS]
    assert gas.native_value == pytest.approx(17.7)
    assert gas.unit_of_measurement == UNIT_KWH
    assert gas.device_class == DEVICE_CLASS_ENERGY


def test_failed_auth_does_not_yield_sensor_values() -> None:
    client = SpGroupClient(
        "user@example.com", "wrong", transport=FixtureTransport(fail_login=True)
    )
    with pytest.raises(AuthError):
        client.fetch_usage()
    assert sensors_from_usage(None) == []
