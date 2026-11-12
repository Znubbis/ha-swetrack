"""Device tracker for SweTrack."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SwetrackConfigEntry, SwetrackCoordinator
from .entity import SwetrackEntity, nested, setup_device_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwetrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one tracker entity per SweTrack device."""
    coordinator = entry.runtime_data

    def _add(device_id: str, device: dict[str, Any]) -> None:
        async_add_entities([SwetrackTracker(coordinator, device_id)])

    entry.async_on_unload(setup_device_entities(coordinator, _add))


class SwetrackTracker(SwetrackEntity, TrackerEntity):
    """The tracker's latest known position."""

    _attr_name = None

    def __init__(self, coordinator: SwetrackCoordinator, device_id: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator, device_id, "tracker")

    @property
    def source_type(self) -> SourceType:
        """Positions come from GPS."""
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        """Latest latitude."""
        return nested(self.device, "position_info", "latitude")

    @property
    def longitude(self) -> float | None:
        """Latest longitude."""
        return nested(self.device, "position_info", "longitude")
