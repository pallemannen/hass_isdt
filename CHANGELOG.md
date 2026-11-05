# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Icons for all entities. Status, verdict, why charging stopped, and the charger event change icon with their state.
- Repairs for hazardous cells: an alkaline that is being charged, and a shorted cell (both errors), and a charge that runs for more than 4 hours (warning). A repair goes away by itself once the slot is empty, or charging stops.
- The charger's build number (the timestamp at the end of its version reply, also part of the PN on its screen) as the device's model ID, and the build date after the hardware version.

## [0.1.0] - 2026-11-04

### Added
- Config flow: host and port of an isdttool bridge. The charger's serial number is the unique ID. Reconfigure to change the address.
- Options: poll interval, and the internal resistance from which a cell counts as worn.
- A device per charger, and one per slot, with status, verdict, voltage, current, progress, charged capacity, charging time, internal resistance, temperature, and the reason why charging stopped.
- Charger event entity: `charged`, `all_charged`, `remove_cell`, `long_charge`.
- Backoff when the bridge is unreachable: 30 s, 1 min, 2 min, then every 5 min.
- Diagnostics.
