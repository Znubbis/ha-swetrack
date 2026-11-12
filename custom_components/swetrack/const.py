"""Constants for the SweTrack integration."""

from __future__ import annotations

import logging

DOMAIN = "swetrack"
LOGGER = logging.getLogger(__package__)

API_BASE_URL = "https://api.cloudappapi.com/publicapi/v1"
REQUEST_TIMEOUT = 30

CONF_SCAN_INTERVAL = "scan_interval"

# The API allows about 1000 calls per token and day. One call per poll:
# 120 s = 720 calls/day, 90 s = 960 calls/day.
DEFAULT_SCAN_INTERVAL = 120
MIN_SCAN_INTERVAL = 90
MAX_SCAN_INTERVAL = 3600

MANUFACTURER = "SweTrack"

# Events are only fetched when a tracker has reported something new, and only
# while the quota still covers the position polls until reset plus this margin.
EVENT_QUOTA_RESERVE = 50
# Events older than this when we first see them are not fired (for example
# after a quota pause), so automations don't react to stale alarms.
EVENT_MAX_AGE_MINUTES = 15
SIGNAL_EVENT = "swetrack_event_{}"
