"""Diagnostics for SweTrack."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import SwetrackConfigEntry

TO_REDACT = {
    "api_token",
    "email",
    "id",
    "latitude",
    "longitude",
    "name",
    "shared_with",
    "uniqueid",
    "username",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwetrackConfigEntry
) -> dict[str, Any]:
    """Return diagnostics with tokens, identities and positions removed."""
    coordinator = entry.runtime_data
    return {
        "options": dict(entry.options),
        "api_usage": coordinator.api.usage,
        "devices": async_redact_data(list(coordinator.data.values()), TO_REDACT),
    }
