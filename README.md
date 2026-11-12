# SweTrack for Home Assistant

Unofficial Home Assistant integration for [SweTrack](https://www.swetrack.com) GPS
trackers. It reads your trackers from SweTrack's
[public API](https://apidoc.swetrack.com/tracking/swetrack/) and is not made or
supported by SweTrack.

## What you get

For every tracker on the account:

| Entity | Notes |
| --- | --- |
| Device tracker | Latest known position |
| Speed | km/h |
| Last position | When the latest position was taken |
| Battery | Internal battery, % |
| External voltage | Only on trackers wired to a vehicle battery |
| Ignition, External power, Relay | Only where the model reports them |
| Online, Power saving mode, Last contact | Diagnostic |

Plus one sensor for the account: **API calls remaining today**.

This version only reads. It does not change the relay, power saving mode or speed limit.

## Install

With [HACS](https://hacs.xyz): add `https://github.com/Znubbis/ha-swetrack` as a custom
repository of type *Integration*, install **SweTrack** and restart Home Assistant.

Manually: copy `custom_components/swetrack` into the `custom_components` folder in your
Home Assistant config directory and restart.

## Set up

1. In the SweTrack app, open **Profile → API**, switch API on, reveal the key and copy it.
2. In Home Assistant, go to **Settings → Devices & services → Add integration** and pick
   **SweTrack**.
3. Paste the key.

An account has one API key at a time. Refreshing it in the app invalidates the old one, and
Home Assistant then asks for the new key.

## Update interval and the daily quota

SweTrack allows about 1000 API calls per key and day. The integration makes one call per
update and updates every 120 seconds by default (720 calls a day). You can change the
interval under **Configure** on the integration; the shortest allowed is 90 seconds.

If the quota runs out, the integration stops calling the API until the quota resets and
the entities become unavailable in the meantime. Other tools that use the same key share
the same quota.

A tracker in power saving mode sleeps between movements and shows as offline. Its entities
keep the last values it reported.
