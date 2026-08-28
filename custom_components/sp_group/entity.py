"""Shared SP Group entity base."""

# mypy: ignore-errors

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SpGroupCoordinator


class SpGroupEntity(CoordinatorEntity[SpGroupCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: SpGroupCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        usage = coordinator.data
        premise_id = usage.premise_id if usage else "unknown"
        address = usage.premise.address if usage else None
        premise_type = usage.premise.premise_type if usage else None
        self._attr_unique_id = f"{premise_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, premise_id)},
            name=address or "SP Group utilities",
            manufacturer="SP Group",
            model=premise_type or "e-account",
        )
        self._attr_translation_key = key
