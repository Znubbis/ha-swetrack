"""The SweTrack integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SwetrackApi
from .coordinator import SwetrackConfigEntry, SwetrackCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: SwetrackConfigEntry) -> bool:
    """Set up SweTrack from a config entry."""
    api = SwetrackApi(async_get_clientsession(hass), entry.data[CONF_API_TOKEN])
    coordinator = SwetrackCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    _async_remove_replaced_entities(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SwetrackConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_options(
    hass: HomeAssistant, entry: SwetrackConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


@callback
def _async_remove_replaced_entities(
    hass: HomeAssistant, entry: SwetrackConfigEntry
) -> None:
    """Remove the 0.1.0 power saving binary sensor; it is a switch now."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain == Platform.BINARY_SENSOR and entity.unique_id.endswith(
            "_powersaving_mode"
        ):
            registry.async_remove(entity.entity_id)
