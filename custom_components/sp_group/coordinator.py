"""Poll SP Group usage on a fixed interval."""

# mypy: ignore-errors

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthError, SpGroupClient, UsageError, UsageReadings
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class SpGroupCoordinator(DataUpdateCoordinator[UsageReadings]):
    def __init__(
        self, hass: HomeAssistant, client: SpGroupClient, entry: ConfigEntry
    ) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> UsageReadings:
        try:
            usage = await self.hass.async_add_executor_job(self.client.fetch_usage)
        except AuthError as exc:
            if exc.error == "requires_verification":
                raise UpdateFailed(str(exc)) from exc
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except UsageError as exc:
            raise UpdateFailed(str(exc)) from exc
        session = self.client.session
        if session is not None:
            data = {
                CONF_USERNAME: self.entry.data[CONF_USERNAME],
                CONF_PASSWORD: self.entry.data[CONF_PASSWORD],
                CONF_ACCESS_TOKEN: session.access_token,
                CONF_ID_TOKEN: session.id_token,
            }
            if session.refresh_token:
                data[CONF_REFRESH_TOKEN] = session.refresh_token
            self.hass.config_entries.async_update_entry(self.entry, data=data)
        return usage
