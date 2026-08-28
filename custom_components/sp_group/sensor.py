"""Energy and water sensors for the Energy dashboard."""

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_KEY_ELECTRICITY, SENSOR_KEY_WATER
from .coordinator import SpGroupCoordinator
from .mapper import extra_attributes, sensors_from_usage

_DEVICE_CLASS = {
    "energy": SensorDeviceClass.ENERGY,
    "water": SensorDeviceClass.WATER,
}
_STATE_CLASS = {
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
}
_UNITS = {
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "m³": UnitOfVolume.CUBIC_METERS,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SpGroupCoordinator = hass.data[DOMAIN][entry.entry_id]
    usage = coordinator.data
    specs = sensors_from_usage(usage)
    if not specs:
        return
    entities = [
        SpGroupSensor(
            coordinator,
            spec.key,
            spec.name,
            spec.device_class,
            spec.unit_of_measurement,
        )
        for spec in specs
    ]
    async_add_entities(entities)


class SpGroupSensor(CoordinatorEntity[SpGroupCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_attribution = "Data provided by SP Group"

    def __init__(
        self,
        coordinator: SpGroupCoordinator,
        key: str,
        name: str,
        device_class: str,
        unit: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self.entity_description = SensorEntityDescription(
            key=key,
            name=name,
            device_class=_DEVICE_CLASS[device_class],
            state_class=_STATE_CLASS["total_increasing"],
            native_unit_of_measurement=_UNITS[unit],
        )
        premise = coordinator.data.premise_id if coordinator.data else "unknown"
        self._attr_unique_id = f"{premise}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, premise)},
            name="SP Group utilities",
            manufacturer="SP Group",
            model="e-account",
        )

    @property
    def native_value(self) -> float | None:
        usage = self.coordinator.data
        if usage is None:
            return None
        if self._key == SENSOR_KEY_ELECTRICITY:
            return usage.electricity_kwh
        if self._key == SENSOR_KEY_WATER:
            return usage.water_m3
        return None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        usage = self.coordinator.data
        if usage is None:
            return {}
        return extra_attributes(usage, self._key)
