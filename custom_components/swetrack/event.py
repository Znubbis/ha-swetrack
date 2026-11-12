"""Event entities for SweTrack."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_EVENT
from .coordinator import SwetrackConfigEntry, SwetrackCoordinator
from .entity import SwetrackEntity, nested, setup_device_entities

OTHER = "other"

# The API's event types (deviceOnline, geofenceEnter, ...) in snake_case.
EVENT_TYPES = [
    "alarmcenter",
    "device_charge_off",
    "device_charge_on",
    "device_hum_below",
    "device_hum_exceeded",
    "device_light_off",
    "device_light_on",
    # Not in the API docs, but sent while the tracker is moving.
    "device_moving",
    "device_offline",
    "device_online",
    "device_overspeed",
    "device_sleep_on",
    "device_temp_below",
    "device_temp_exceeded",
    "device_wake",
    "geofence_enter",
    "geofence_exit",
    "ignition_off",
    "ignition_on",
    "low_battery",
    "power_cut",
    "power_off",
    "power_on",
    "psmsafetyzone",
    "tampering",
    "vibration",
    OTHER,
]


def _snake(value: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value).lower()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwetrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one event entity per SweTrack device."""
    coordinator = entry.runtime_data

    def _add(device_id: str, device: dict[str, Any]) -> None:
        async_add_entities([SwetrackEvent(coordinator, device_id)])

    entry.async_on_unload(setup_device_entities(coordinator, _add))


class SwetrackEvent(SwetrackEntity, EventEntity):
    """Fires for every new event SweTrack records for the tracker."""

    _attr_translation_key = "event"
    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: SwetrackCoordinator, device_id: str) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, device_id, "event")

    async def async_added_to_hass(self) -> None:
        """Listen for events the coordinator finds for this tracker."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_EVENT.format(self._device_id), self._async_handle
            )
        )

    @callback
    def _async_handle(self, event: dict[str, Any]) -> None:
        raw_type = str(event.get("type") or "")
        event_type = _snake(raw_type)
        if event_type not in EVENT_TYPES:
            event_type = OTHER

        attributes: dict[str, Any] = {
            "swetrack_type": raw_type,
            "description": event.get("description"),
            "event_time": event.get("eventtime"),
        }
        if nested(event, "position", "exists"):
            attributes["latitude"] = nested(event, "position", "latitude")
            attributes["longitude"] = nested(event, "position", "longitude")
        # additionalinfo looks like {"reason": {"value": ...}} or
        # {"speed": {"value": "95", "unit": "km/h"}}; keep the values.
        for key, info in (event.get("additionalinfo") or {}).items():
            attributes[key] = info.get("value") if isinstance(info, dict) else info

        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
