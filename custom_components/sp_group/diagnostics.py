"""Redacted diagnostics for a config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_REFRESH_TOKEN
from .coordinator import SpGroupCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: SpGroupCoordinator = entry.runtime_data
    usage = coordinator.data
    if usage is None:
        return {
            "has_refresh_token": bool(entry.data.get(CONF_REFRESH_TOKEN)),
            "usage": None,
        }
    return {
        "has_refresh_token": bool(entry.data.get(CONF_REFRESH_TOKEN)),
        "premise_id": usage.premise_id,
        "has_address": bool(usage.premise.address),
        "has_account_number": bool(usage.premise.account_number),
        "account_status": usage.premise.account_status,
        "account_type": usage.premise.account_type,
        "premise_type": usage.premise.premise_type,
        "utilities": list(usage.premise.utilities),
        "ami_elec": usage.premise.ami_elec,
        "has_retailer": bool(usage.premise.retailer_name),
        "ppms_exists": usage.premise.ppms_exists,
        "ppms_credit": usage.ppms_credit,
        "electricity_kwh": usage.electricity_kwh,
        "water_m3": usage.water_m3,
        "has_gas": usage.gas is not None,
        "electricity_periods": len(usage.electricity_periods),
        "water_periods": len(usage.water_periods),
        "gas_periods": len(usage.gas_periods),
        "has_meter_reading": usage.meter_reading is not None,
    }
