"""Energy, water, gas, and account sensors."""

# mypy: ignore-errors

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SpGroupCoordinator
from .entity import SpGroupEntity
from .mapper import extra_attributes, sensors_from_usage

PARALLEL_UPDATES = 0

_DEVICE_CLASS = {
    "energy": SensorDeviceClass.ENERGY,
    "water": SensorDeviceClass.WATER,
    "gas": SensorDeviceClass.GAS,
    "monetary": SensorDeviceClass.MONETARY,
}
_STATE_CLASS = {
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
    "measurement": SensorStateClass.MEASUREMENT,
}
_UNITS = {
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "m³": UnitOfVolume.CUBIC_METERS,
    "SGD": "SGD",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpGroupCoordinator = entry.runtime_data
    usage = coordinator.data
    specs = sensors_from_usage(usage)
    if not specs:
        return
    async_add_entities([SpGroupSensor(coordinator, spec.key) for spec in specs])


class SpGroupSensor(SpGroupEntity, SensorEntity):
    def __init__(self, coordinator: SpGroupCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        spec = self._current_spec()
        device_class = _DEVICE_CLASS.get(spec.device_class) if spec else None
        state_class = None
        if spec is not None and spec.state_class:
            state_class = _STATE_CLASS.get(spec.state_class)
        unit = None
        if spec is not None and spec.unit_of_measurement:
            unit = _UNITS.get(spec.unit_of_measurement, spec.unit_of_measurement)
        category = None
        if spec is not None and spec.entity_category == "diagnostic":
            category = EntityCategory.DIAGNOSTIC
        self.entity_description = SensorEntityDescription(
            key=key,
            device_class=device_class,
            state_class=state_class,
            native_unit_of_measurement=unit,
            entity_category=category,
            suggested_display_precision=(
                spec.suggested_display_precision if spec else None
            ),
        )

    def _current_spec(self):
        return next(
            (
                spec
                for spec in sensors_from_usage(self.coordinator.data)
                if spec.key == self._key
            ),
            None,
        )

    @property
    def native_value(self) -> float | str | None:
        spec = self._current_spec()
        return spec.native_value if spec else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        usage = self.coordinator.data
        if usage is None:
            return {}
        return extra_attributes(usage, self._key)
