"""Poll SP Group usage on a fixed interval."""

# mypy: ignore-errors

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthError, SpGroupClient, UsageError, UsageReadings
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SpGroupCoordinator(DataUpdateCoordinator[UsageReadings]):
    def __init__(self, hass: HomeAssistant, client: SpGroupClient) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> UsageReadings:
        try:
            return await self.hass.async_add_executor_job(self.client.fetch_usage)
        except AuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except UsageError as exc:
            raise UpdateFailed(str(exc)) from exc
