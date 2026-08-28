"""Map Jarvis usage readings onto Energy-dashboard sensor specs."""

from __future__ import annotations

from dataclasses import dataclass

from .client import UsageReadings
from .const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_WATER,
    SENSOR_KEY_ELECTRICITY,
    SENSOR_KEY_WATER,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_M3,
)


@dataclass(frozen=True)
class SensorSpec:
    key: str
    name: str
    native_value: float
    device_class: str
    state_class: str
    unit_of_measurement: str


def sensors_from_usage(usage: UsageReadings | None) -> list[SensorSpec]:
    """Return energy/water sensors, or none if login/usage failed."""
    if usage is None:
        return []
    return [
        SensorSpec(
            key=SENSOR_KEY_ELECTRICITY,
            name="Electricity",
            native_value=usage.electricity_kwh,
            device_class=DEVICE_CLASS_ENERGY,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            unit_of_measurement=UNIT_KWH,
        ),
        SensorSpec(
            key=SENSOR_KEY_WATER,
            name="Water",
            native_value=usage.water_m3,
            device_class=DEVICE_CLASS_WATER,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            unit_of_measurement=UNIT_M3,
        ),
    ]
