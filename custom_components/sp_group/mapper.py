"""Map Jarvis usage readings onto Energy-dashboard sensor specs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .client import SG_TZ, PeriodReading, UsageReadings, UtilitySeries
from .const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_WATER,
    ENTITY_CATEGORY_DIAGNOSTIC,
    SENSOR_KEY_ACCOUNT,
    SENSOR_KEY_AMOUNT_DUE,
    SENSOR_KEY_ELECTRICITY,
    SENSOR_KEY_ELECTRICITY_GOAL,
    SENSOR_KEY_ELECTRICITY_HOUR,
    SENSOR_KEY_ELECTRICITY_LAST,
    SENSOR_KEY_ELECTRICITY_METER,
    SENSOR_KEY_ELECTRICITY_TODAY,
    SENSOR_KEY_GAS,
    SENSOR_KEY_GAS_LAST,
    SENSOR_KEY_LAST_BILL,
    SENSOR_KEY_PPMS,
    SENSOR_KEY_WATER,
    SENSOR_KEY_WATER_GOAL,
    SENSOR_KEY_WATER_LAST,
    SENSOR_KEY_WATER_METER,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_M3,
    UNIT_SGD,
)
from .history import fold_half_hours, merge_ami_periods, trim_unreported


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


def reported_ami_slots(usage: UsageReadings) -> tuple[PeriodReading, ...]:
    return trim_unreported(usage.ami_hourly)


def electricity_graph_periods(usage: UsageReadings) -> tuple[PeriodReading, ...]:
    hourly = fold_half_hours(reported_ami_slots(usage))
    merged = merge_ami_periods(usage.ami_daily, hourly)
    if merged:
        return merged
    return usage.electricity.periods if usage.electricity else ()


def _today_kwh(usage: UsageReadings) -> float | None:
    slots = reported_ami_slots(usage)
    if not slots:
        return None
    today = datetime.now(SG_TZ).date()
    return sum(
        item.amount for item in slots if item.start.astimezone(SG_TZ).date() == today
    )


def _last_interval(usage: UsageReadings) -> PeriodReading | None:
    slots = reported_ami_slots(usage)
    if not slots:
        return None
    return max(slots, key=lambda item: item.start)


def _last_hour_kwh(usage: UsageReadings) -> float | None:
    last = _last_interval(usage)
    return last.amount if last is not None else None


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
    if key == SENSOR_KEY_LAST_BILL:
        bill = usage.last_bill
        if bill is not None:
            attrs["bill_date"] = bill.date
            attrs["bill_period"] = bill.period
            attrs["due_date"] = bill.due_date
            attrs["bill_account_number"] = bill.account_number
        return _omit_none(attrs)
    if key == SENSOR_KEY_AMOUNT_DUE:
        due = usage.amount_due
        if due is not None:
            attrs["currency"] = due.currency
            attrs["giro_enabled"] = due.giro_enabled
            attrs["recurring_enabled"] = due.recurring_enabled
        return _omit_none(attrs)
    if key == SENSOR_KEY_ELECTRICITY_METER:
        meter = usage.meter("electric")
        if meter is not None:
            attrs["meter_id"] = meter.meter_id
            attrs["last_actual_at"] = meter.last_actual_at
        return _omit_none(attrs)
    if key == SENSOR_KEY_WATER_METER:
        meter = usage.meter("water")
        if meter is not None:
            attrs["meter_id"] = meter.meter_id
            attrs["last_actual_at"] = meter.last_actual_at
        return _omit_none(attrs)
    if key == SENSOR_KEY_ELECTRICITY_GOAL:
        goal = usage.goal("elec")
        if goal is not None:
            attrs["goal_month"] = goal.month
            attrs["goal_target"] = goal.target
            attrs["percent_difference"] = goal.percent_difference
            attrs["cost_difference_sgd"] = goal.cost_difference_sgd
        return _omit_none(attrs)
    if key == SENSOR_KEY_WATER_GOAL:
        goal = usage.goal("water")
        if goal is not None:
            attrs["goal_month"] = goal.month
            attrs["goal_target"] = goal.target
            attrs["percent_difference"] = goal.percent_difference
            attrs["cost_difference_sgd"] = goal.cost_difference_sgd
        return _omit_none(attrs)
    series: UtilitySeries | None
    if key in {
        SENSOR_KEY_ELECTRICITY,
        SENSOR_KEY_ELECTRICITY_LAST,
        SENSOR_KEY_ELECTRICITY_TODAY,
        SENSOR_KEY_ELECTRICITY_HOUR,
    }:
        series = usage.electricity
        if key == SENSOR_KEY_ELECTRICITY:
            graph = electricity_graph_periods(usage)
            if graph:
                last = _last_period(graph)
                attrs["period_count"] = len(graph)
                attrs["ami_half_hour_count"] = len(usage.ami_hourly)
                attrs["ami_daily_count"] = len(usage.ami_daily)
                if last is not None:
                    attrs["last_period"] = last.start.isoformat()
                    attrs["last_period_amount"] = last.amount
                today = _today_kwh(usage)
                if today is not None:
                    attrs["today_kwh"] = today
                last_slot = _last_interval(usage)
                if last_slot is not None:
                    attrs["last_interval"] = last_slot.start.isoformat()
                    attrs["last_interval_kwh"] = last_slot.amount
                return _omit_none(attrs)
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


def _last_spec(key: str, series: UtilitySeries, precision: int) -> SensorSpec:
    last = _last_period(series.periods)
    return SensorSpec(
        key=key,
        translation_key=key,
        native_value=last.amount if last is not None else None,
        device_class=None,
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
        graph = electricity_graph_periods(usage)
        elec_total = (
            sum(item.amount for item in graph) if graph else usage.electricity.total
        )
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_ELECTRICITY,
                translation_key=SENSOR_KEY_ELECTRICITY,
                native_value=elec_total,
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=UNIT_KWH,
                suggested_display_precision=1,
            )
        )
        specs.append(_last_spec(SENSOR_KEY_ELECTRICITY_LAST, usage.electricity, 1))
        today = _today_kwh(usage)
        if today is not None:
            specs.append(
                SensorSpec(
                    key=SENSOR_KEY_ELECTRICITY_TODAY,
                    translation_key=SENSOR_KEY_ELECTRICITY_TODAY,
                    native_value=today,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    unit_of_measurement=UNIT_KWH,
                    suggested_display_precision=2,
                )
            )
        hour = _last_hour_kwh(usage)
        if hour is not None:
            specs.append(
                SensorSpec(
                    key=SENSOR_KEY_ELECTRICITY_HOUR,
                    translation_key=SENSOR_KEY_ELECTRICITY_HOUR,
                    native_value=hour,
                    device_class=None,
                    state_class=STATE_CLASS_MEASUREMENT,
                    unit_of_measurement=UNIT_KWH,
                    suggested_display_precision=2,
                )
            )
    if usage.water is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_WATER,
                translation_key=SENSOR_KEY_WATER,
                native_value=usage.water.total,
                device_class=DEVICE_CLASS_WATER,
                state_class=None,
                unit_of_measurement=UNIT_M3,
                suggested_display_precision=2,
            )
        )
        specs.append(_last_spec(SENSOR_KEY_WATER_LAST, usage.water, 2))
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
        specs.append(_last_spec(SENSOR_KEY_GAS_LAST, usage.gas, precision))
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
    if usage.last_bill is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_LAST_BILL,
                translation_key=SENSOR_KEY_LAST_BILL,
                native_value=usage.last_bill.amount_sgd,
                device_class=DEVICE_CLASS_MONETARY,
                state_class=None,
                unit_of_measurement=UNIT_SGD,
                suggested_display_precision=2,
            )
        )
    if usage.amount_due is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_AMOUNT_DUE,
                translation_key=SENSOR_KEY_AMOUNT_DUE,
                native_value=usage.amount_due.amount_sgd,
                device_class=DEVICE_CLASS_MONETARY,
                state_class=None,
                unit_of_measurement=UNIT_SGD,
                suggested_display_precision=2,
            )
        )
    elec_meter = usage.meter("electric")
    if elec_meter is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_ELECTRICITY_METER,
                translation_key=SENSOR_KEY_ELECTRICITY_METER,
                native_value=elec_meter.value,
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=UNIT_KWH,
                suggested_display_precision=0,
            )
        )
    water_meter = usage.meter("water")
    if water_meter is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_WATER_METER,
                translation_key=SENSOR_KEY_WATER_METER,
                native_value=water_meter.value,
                device_class=DEVICE_CLASS_WATER,
                state_class=STATE_CLASS_TOTAL_INCREASING,
                unit_of_measurement=UNIT_M3,
                suggested_display_precision=1,
            )
        )
    elec_goal = usage.goal("elec")
    if elec_goal is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_ELECTRICITY_GOAL,
                translation_key=SENSOR_KEY_ELECTRICITY_GOAL,
                native_value=elec_goal.used,
                device_class=None,
                state_class=STATE_CLASS_MEASUREMENT,
                unit_of_measurement=UNIT_KWH,
                suggested_display_precision=1,
            )
        )
    water_goal = usage.goal("water")
    if water_goal is not None:
        specs.append(
            SensorSpec(
                key=SENSOR_KEY_WATER_GOAL,
                translation_key=SENSOR_KEY_WATER_GOAL,
                native_value=water_goal.used,
                device_class=None,
                state_class=STATE_CLASS_MEASUREMENT,
                unit_of_measurement=UNIT_M3,
                suggested_display_precision=2,
            )
        )
    return specs
