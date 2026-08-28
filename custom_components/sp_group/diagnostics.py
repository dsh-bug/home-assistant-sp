"""Redacted diagnostics for a config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import SpGroupCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: SpGroupCoordinator = hass.data[DOMAIN][entry.entry_id]
    usage = coordinator.data
    return {
        "has_refresh_token": bool(entry.data.get(CONF_REFRESH_TOKEN)),
        "premise_id": usage.premise_id if usage else None,
        "electricity_kwh": usage.electricity_kwh if usage else None,
        "water_m3": usage.water_m3 if usage else None,
        "electricity_periods": (len(usage.electricity_periods) if usage else 0),
        "water_periods": len(usage.water_periods) if usage else 0,
    }
