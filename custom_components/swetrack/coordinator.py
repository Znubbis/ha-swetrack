"""Data update coordinator for SweTrack."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    SwetrackApi,
    SwetrackAuthError,
    SwetrackError,
    SwetrackRateLimitError,
)
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type SwetrackConfigEntry = ConfigEntry[SwetrackCoordinator]


class SwetrackCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Polls /devices/info and keeps the devices keyed by device id."""

    config_entry: SwetrackConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: SwetrackConfigEntry, api: SwetrackApi
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api
        self._quota_blocked_until: datetime | None = None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        now = dt_util.utcnow()
        if self._quota_blocked_until and now < self._quota_blocked_until:
            raise UpdateFailed(
                f"Daily API quota used up, waiting until {self._quota_blocked_until}"
            )
        self._quota_blocked_until = None

        try:
            devices = await self.api.async_get_devices()
        except SwetrackAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SwetrackRateLimitError as err:
            # Don't spend more calls until the quota resets.
            self._quota_blocked_until = err.reset_at or now + timedelta(hours=1)
            raise UpdateFailed(f"Daily API quota used up: {err}") from err
        except SwetrackError as err:
            raise UpdateFailed(str(err)) from err

        return {device["id"]: device for device in devices}
