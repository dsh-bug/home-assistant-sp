"""Map Jarvis usage readings onto Energy-dashboard sensor specs."""

from __future__ import annotations

from dataclasses import dataclass

from .client import PeriodReading, UsageReadings, UtilitySeries
from .const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_WATER,
    ENTITY_CATEGORY_DIAGNOSTIC,
    SENSOR_KEY_ACCOUNT,
    SENSOR_KEY_ELECTRICITY,
    SENSOR_KEY_ELECTRICITY_LAST,
    SENSOR_KEY_GAS,
    SENSOR_KEY_GAS_LAST,
    SENSOR_KEY_PPMS,
    SENSOR_KEY_WATER,
    SENSOR_KEY_WATER_LAST,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_M3,
    UNIT_SGD,
)


@dataclass(frozen=True)
class SensorSpec:
    key: str
    translation_key: str
    native_value: float | str | None
    device_class: str | None
    state_class: str | None
    unit_of_measurement: str | None
    entity_category: str | None = None
    suggested_display_precision: int | None = None


def _last_period(periods: tuple[PeriodReading, ...]) -> PeriodReading | None:
    if not periods:
        return None
    return max(periods, key=lambda item: item.start)


def _omit_none(attrs: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in attrs.items() if value is not None}


def _series_device_class(series: UtilitySeries, kind: str) -> str:
    if kind == "elec":
        return DEVICE_CLASS_ENERGY
    if kind == "water":
        return DEVICE_CLASS_WATER
    if series.unit == UNIT_KWH:
        return DEVICE_CLASS_ENERGY
    return DEVICE_CLASS_GAS


def extra_attributes(usage: UsageReadings, key: str) -> dict[str, object]:
    """Premise metadata plus last billed period for the matching utility."""
    premise = usage.premise
    attrs: dict[str, object] = {
        "premise_id": premise.id,
        "address": premise.address,
        "account_number": premise.account_number,
        "account_status": premise.account_status,
        "account_type": premise.account_type,
        "premise_type": premise.premise_type,
        "utilities": list(premise.utilities) if premise.utilities else None,
        "ami_elec": premise.ami_elec,
        "retailer_name": premise.retailer_name,
    }
    if key == SENSOR_KEY_ACCOUNT:
        reading = usage.meter_reading
        if reading is not None:
            attrs["meter_reading_message"] = reading.message
            attrs["meter_reading_title"] = reading.title
            attrs["meter_reading_start"] = reading.start
            attrs["meter_reading_end"] = reading.end
        return _omit_none(attrs)
    series: UtilitySeries | None
    if key in {SENSOR_KEY_ELECTRICITY, SENSOR_KEY_ELECTRICITY_LAST}:
        series = usage.electricity
    elif key in {SENSOR_KEY_WATER, SENSOR_KEY_WATER_LAST}:
        series = usage.water
    elif key in {SENSOR_KEY_GAS, SENSOR_KEY_GAS_LAST}:
        series = usage.gas
    else:
        series = None
    if series is None:
        return _omit_none(attrs)
    last = _last_period(series.periods)
    attrs["average_consumption"] = series.average
    attrs["comparison"] = series.comparison
    attrs["period_count"] = len(series.periods)
    if last is not None:
        attrs["last_period"] = last.start.isoformat()
        attrs["last_period_amount"] = last.amount
        attrs["last_period_previous"] = last.previous
        attrs["last_period_status"] = last.status
    return _omit_none(attrs)


def _last_spec(
    key: str, series: UtilitySeries, kind: str, precision: int
) -> SensorSpec:
    last = _last_period(series.periods)
    return SensorSpec(
        key=key,
        translation_key=key,
        native_value=last.amount if last is not None else None,
        device_class=_series_device_class(series, kind),
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement=series.unit,
        suggested_display_precision=precision,
    )


def sensors_from_usage(usage: UsageReadings | None) -> list[SensorSpec]:
    """Return energy/water/gas sensors plus account diagnostics."""
    if usage is None:
        return []
    specs: list[SensorSpec] = []
    if usage.electricity is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_ELECTRICITY,
                translation_key=SENSOR_KEY_ELECTRICITY,
                native_value=usage.electricity.total,
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=UNIT_KWH,
                suggested_display_precision=1,
            )
        )
        specs.append(
            _last_spec(SENSOR_KEY_ELECTRICITY_LAST, usage.electricity, "elec", 1)
        )
    if usage.water is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_WATER,
                translation_key=SENSOR_KEY_WATER,
                native_value=usage.water.total,
                device_class=DEVICE_CLASS_WATER,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=UNIT_M3,
                suggested_display_precision=2,
            )
        )
        specs.append(_last_spec(SENSOR_KEY_WATER_LAST, usage.water, "water", 2))
    if usage.gas is not None:
        gas_class = _series_device_class(usage.gas, "gas")
        precision = 1 if usage.gas.unit == UNIT_KWH else 2
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_GAS,
                translation_key=SENSOR_KEY_GAS,
                native_value=usage.gas.total,
                device_class=gas_class,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=usage.gas.unit,
                suggested_display_precision=precision,
            )
        )
        specs.append(_last_spec(SENSOR_KEY_GAS_LAST, usage.gas, "gas", precision))
    specs.append(
        SensorSpec(
            key=SENSOR_KEY_ACCOUNT,
            translation_key=SENSOR_KEY_ACCOUNT,
            native_value=usage.premise.account_status or "unknown",
            device_class=None,
            state_class=None,
            unit_of_measurement=None,
            entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        )
    )
    if usage.ppms_credit is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_PPMS,
                translation_key=SENSOR_KEY_PPMS,
                native_value=usage.ppms_credit,
                device_class=DEVICE_CLASS_MONETARY,
                state_class=None,
                unit_of_measurement=UNIT_SGD,
                entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
                suggested_display_precision=2,
            )
        )
    return specs
