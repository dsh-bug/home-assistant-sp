"""SP Group Home Assistant integration."""

# mypy: ignore-errors

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
    from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

    from .client import AuthError, Session, SpGroupClient, UsageError
    from .const import CONF_ACCESS_TOKEN, CONF_ID_TOKEN, CONF_REFRESH_TOKEN
    from .coordinator import SpGroupCoordinator

    access = entry.data.get(CONF_ACCESS_TOKEN)
    ident = entry.data.get(CONF_ID_TOKEN)
    refresh = entry.data.get(CONF_REFRESH_TOKEN)
    session = None
    if isinstance(access, str) and isinstance(ident, str) and access and ident:
        session = Session(
            access_token=access,
            id_token=ident,
            refresh_token=refresh if isinstance(refresh, str) else None,
            scope=None,
        )
    client = SpGroupClient(
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )
    coordinator = SpGroupCoordinator(hass, client, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except AuthError as exc:
        if exc.error == "requires_verification":
            raise ConfigEntryNotReady(str(exc)) from exc
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except UsageError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True
