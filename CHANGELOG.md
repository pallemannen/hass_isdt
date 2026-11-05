# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Rejected cells count. Every slot is now in exactly one of Free slots, Cells charging, Cells charged, Invalid cells, and Rejected cells, so they always add up to the number of slots.
- Charger counts: Slots, Free slots, Cells charging, Cells charged, Invalid cells.
- Icons for all entities. Status, verdict, why charging stopped, and the charger event change icon with their state.
- Repairs for hazardous cells: an alkaline that is being charged, and a shorted cell (both errors), and a charge that runs for more than 4 hours (warning). A repair goes away by itself once the slot is empty, or charging stops.
- The charger's build number (the timestamp at the end of its version reply, also part of the PN on its screen) as the device's model ID, and the build date after the hardware version.

### Removed
- The Charging slots count, replaced by Cells charging. "Charging slots" was ambiguous.

### Fixed
- An alkaline that the charger stopped after a short pulse, or refused, was reported as worn, or rejected, not as possibly alkaline. A cell that never charged normally, with an internal resistance of 1000 mΩ or more, is now possibly alkaline, and raises a repair. Healthy NiMH cells read 150–300 mΩ.
- Polls failed most of the time while cells were charging, which made all entities
  unavailable. A busy N24 now and then answers late, or not at all. Late replies are now
  recognised and skipped, a missed request is retried up to twice, and isdttool-pal 1.1.2
  waits up to 1 s for a reply over the network.
- Polls no longer ask the charger what model it is, every time.
- Slot devices are created with `via_device_id`. The `via_device` way is deprecated, and
  stops working in Home Assistant 2027.8.

## [0.1.0] - 2026-11-04

### Added
- Config flow: host and port of an isdttool bridge. The charger's serial number is the unique ID. Reconfigure to change the address.
- Options: poll interval, and the internal resistance from which a cell counts as worn.
- A device per charger, and one per slot, with status, verdict, voltage, current, progress, charged capacity, charging time, internal resistance, temperature, and the reason why charging stopped.
- Charger event entity: `charged`, `all_charged`, `remove_cell`, `long_charge`.
- Backoff when the bridge is unreachable: 30 s, 1 min, 2 min, then every 5 min.
- Diagnostics.
