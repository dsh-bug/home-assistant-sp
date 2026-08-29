"""Poll SP Group usage on a fixed interval."""

# mypy: ignore-errors

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import AuthError, SpGroupClient, UsageError, UsageReadings, UtilitySeries
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ID_TOKEN,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    SENSOR_KEY_ELECTRICITY,
    SENSOR_KEY_GAS,
    UNIT_KWH,
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
        self._platforms_ready = False
        self._stats_lock = asyncio.Lock()
        self._stats_task: asyncio.Task[None] | None = None

    def mark_platforms_ready(self) -> None:
        self._platforms_ready = True

    async def _async_update_data(self) -> UsageReadings:
        try:
            usage = await self.hass.async_add_executor_job(self.client.fetch_usage)
        except AuthError as exc:
            if exc.error == "requires_verification":
                raise UpdateFailed(str(exc)) from exc
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except UsageError as exc:
            raise UpdateFailed(str(exc)) from exc
        self._persist_session_if_changed()
        if self._platforms_ready:
            self._schedule_stats_import()
        return usage

    def _persist_session_if_changed(self) -> None:
        session = self.client.session
        if session is None:
            return
        data = self.entry.data
        refresh = session.refresh_token or None
        stored_refresh = data.get(CONF_REFRESH_TOKEN) or None
        if (
            data.get(CONF_ACCESS_TOKEN) == session.access_token
            and data.get(CONF_ID_TOKEN) == session.id_token
            and stored_refresh == refresh
        ):
            return
        payload = {
            CONF_USERNAME: data[CONF_USERNAME],
            CONF_PASSWORD: data[CONF_PASSWORD],
            CONF_ACCESS_TOKEN: session.access_token,
            CONF_ID_TOKEN: session.id_token,
        }
        if session.refresh_token:
            payload[CONF_REFRESH_TOKEN] = session.refresh_token
        self.hass.config_entries.async_update_entry(self.entry, data=payload)

    def _schedule_stats_import(self) -> None:
        task = self._stats_task
        if task is not None and not task.done():
            return
        self._stats_task = self.hass.async_create_task(
            self.async_import_billed_history()
        )

    async def async_import_billed_history(self) -> None:
        """Write billed period totals into recorder long-term statistics."""
        async with self._stats_lock:
            usage = self.data
            if usage is None:
                return
            try:
                await self._async_import_billed_history(usage)
            except Exception:
                _LOGGER.exception("failed to import billed statistics")

    def _history_series(
        self, usage: UsageReadings
    ) -> list[tuple[str, tuple, str, str]]:
        from .mapper import electricity_graph_periods

        series: list[tuple[str, tuple, str, str]] = []
        if usage.electricity is not None:
            periods = electricity_graph_periods(usage)
            series.append(
                (
                    SENSOR_KEY_ELECTRICITY,
                    periods if periods else usage.electricity.periods,
                    UNIT_KWH,
                    "energy",
                )
            )
        if usage.gas is not None:
            series.append(
                (
                    SENSOR_KEY_GAS,
                    usage.gas.periods,
                    usage.gas.unit,
                    _unit_class(usage.gas),
                )
            )
        return series

    async def _async_import_billed_history(self, usage: UsageReadings) -> None:
        from homeassistant.components.recorder.models.statistics import (
            StatisticMeanType,
        )
        from homeassistant.components.recorder.statistics import async_import_statistics
        from homeassistant.helpers import entity_registry as er

        from .history import cumulative_points

        registry = er.async_get(self.hass)
        for key, periods, unit, unit_class in self._history_series(usage):
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{usage.premise_id}_{key}"
            )
            if entity_id is None:
                continue
            points = cumulative_points(periods)
            if not points:
                continue
            metadata = {
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
                "name": None,
                "source": "recorder",
                "statistic_id": entity_id,
                "unit_class": unit_class,
                "unit_of_measurement": unit,
            }
            stats = [
                {
                    "start": point.start,
                    "state": point.cumulative,
                    "sum": point.cumulative,
                }
                for point in points
            ]
            async_import_statistics(self.hass, metadata, stats)


def _unit_class(series: UtilitySeries) -> str:
    if series.unit == UNIT_KWH:
        return "energy"
    return "volume"
