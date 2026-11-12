"""Data update coordinator for SweTrack."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    SwetrackApi,
    SwetrackAuthError,
    SwetrackError,
    SwetrackRateLimitError,
)
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_MAX_AGE_MINUTES,
    EVENT_QUOTA_RESERVE,
    LOGGER,
    SIGNAL_EVENT,
)

type SwetrackConfigEntry = ConfigEntry[SwetrackCoordinator]

SEEN_EVENTS_MAX = 500


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
        # What each tracker last reported, to tell when there may be new events.
        self._activity: dict[str, tuple[Any, Any]] | None = None
        self._events_seeded = False
        self._seen_events: set[str] = set()
        self._seen_order: deque[str] = deque()

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

        data = {device["id"]: device for device in devices}
        await self._async_update_events(data)
        return data

    def _quota_allows_events(self) -> bool:
        """Only spend calls on events that the position polls can spare.

        A tracker that is awake all day would otherwise double the call count
        and run the quota dry, which stops positions too.
        """
        usage = self.api.usage
        remaining = usage.get("remaining_requests")
        reset_at = dt_util.parse_datetime(str(usage.get("reset_at")))
        if (
            not isinstance(remaining, int)
            or reset_at is None
            or not self.update_interval
        ):
            return True
        seconds_left = max((reset_at - dt_util.utcnow()).total_seconds(), 0)
        polls_left = seconds_left / self.update_interval.total_seconds()
        return remaining > polls_left + EVENT_QUOTA_RESERVE

    async def _async_update_events(self, data: dict[str, dict[str, Any]]) -> None:
        """Fetch and fire new events, but only when a tracker has been active.

        Events only appear when a tracker talks to SweTrack, and that also moves
        its last_update or status. Skipping the call otherwise keeps a sleeping
        tracker at one API call per poll.
        """
        activity = {
            device_id: (device.get("last_update"), device.get("status"))
            for device_id, device in data.items()
        }
        changed = self._activity is not None and activity != self._activity
        self._activity = activity
        if self._events_seeded and not changed:
            return

        if not self._quota_allows_events():
            return

        try:
            events = await self.api.async_get_events()
        except SwetrackError as err:
            # Positions and sensors are still fine; try again on the next change.
            LOGGER.debug("Could not fetch events: %s", err)
            return

        fire = self._events_seeded
        self._events_seeded = True
        oldest = dt_util.utcnow() - timedelta(minutes=EVENT_MAX_AGE_MINUTES)
        fresh: list[tuple[datetime, dict[str, Any]]] = []
        for event in events:
            event_id = event["id"]
            if event_id in self._seen_events:
                continue
            self._seen_events.add(event_id)
            self._seen_order.append(event_id)
            event_time = dt_util.parse_datetime(str(event.get("eventtime")))
            if fire and event_time and event_time >= oldest:
                fresh.append((event_time, event))
        while len(self._seen_order) > SEEN_EVENTS_MAX:
            self._seen_events.discard(self._seen_order.popleft())

        for _, event in sorted(fresh, key=lambda item: item[0]):
            device_id = (event.get("device") or {}).get("id")
            if device_id:
                async_dispatcher_send(self.hass, SIGNAL_EVENT.format(device_id), event)
