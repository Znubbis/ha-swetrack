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
| Event | Fires for vibration, geofence, ignition, online/offline and the other events SweTrack records |
| Power saving mode (switch) | Only where the model supports it |
| Relay (switch) | Only where the model supports it. Disabled until you enable it |
| Online, Last contact | Diagnostic |

Plus one sensor for the account: **API calls remaining today**.

### Events

The event entity gets a new event every time SweTrack records one for the tracker. Use it
as a trigger in an automation, for example to get a notification when the tracker
reports `vibration` or `geofence_exit` at night. Each event carries its time, a
description, the position if SweTrack has one, and any extra details such as the wake-up
reason or the speed.

Events are checked on the normal update, so they arrive up to one update interval late.
Events older than 15 minutes when they are first seen are not fired.

### Switches

A sleeping tracker cannot be reached, so a change is queued at SweTrack and applied the
next time the tracker is awake. Until then the switch shows the queued value and its
`pending` attribute is true.

The relay normally cuts the vehicle's ignition or fuel supply. Its switch is disabled by
default so that it cannot be flipped by accident; enable it on the device page if you
want it. The read-only Relay sensor always shows the actual state.

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

Events cost one extra call, but only on updates where a tracker has reported something
new. If the calls left would not last until the quota resets, events are skipped so that
positions keep updating.

If the quota runs out, the integration stops calling the API until the quota resets and
the entities become unavailable in the meantime. Other tools that use the same key share
the same quota.

A tracker in power saving mode sleeps between movements and shows as offline. Its entities
keep the last values it reported.
