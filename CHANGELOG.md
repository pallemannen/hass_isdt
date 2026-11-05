# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

## [0.2.0] - 2026-11-05

### Added
- Per slot: **Cell inserted**, **Charging** and **Problem** on/off sensors. Problem is on for invalid and rejected cells.
- Per slot: **Charging since**, when the current charge started.
- Charger: **Total current**, what the charger puts into all cells together.
- The slots are put in the charger's area, and move with it. A slot put in another area on purpose stays there.
- Blueprint **ISDT charger event**: runs actions on a charger event, all slots charged by default.
- Tests, replaying the logged replies of an N24 during 85 charges of real cells. They run on GitHub.
- README: tested models, related projects, disclaimer.

### Changed
- Progress is a battery level, so it gets battery icons and works with battery cards.
- Charging time is diagnostic, and disabled for new installations: it changes with every poll, and Charging since tells the same. Disable it by hand on an existing installation if you don't use it.

## [0.1.1] - 2026-11-04

### Added
- Temperature of the charger itself, on the charger device: the highest of the temperatures it measures. While charging, they differ by up to 4 °C between slots.

## [0.1.0] - 2026-11-04

First release. Monitors an ISDT charger, slot by slot, through an isdttool bridge. Developed with the ISDT N24.

### Added
- Config flow with the host and port of an isdttool bridge. The charger's serial number is the unique ID. Reconfigure changes the address.
- Options: poll interval, and the internal resistance from which a cell counts as worn.
- A device per charger, with the build number as model ID, and the build date after the hardware version.
- A device per slot, with status, verdict, voltage, current, progress, charged capacity, charging time, internal resistance, temperature, and why charging stopped.
- Verdict per insertion: good, worn, rejected, possibly alkaline, shorted.
- Charger counts: Slots, and Free slots, Cells charging, Cells charged, Invalid cells, and Rejected cells, which always add up to the number of slots.
- Charger event entity: `charged`, `all_charged`, `remove_cell`, `long_charge`.
- Repairs for an alkaline, or a shorted cell, in a slot (errors), and for a charge longer than 4 hours (warning). They go away by themselves.
- Icons for all entities.
- Polling that copes with a busy charger: late replies are skipped, missed requests retried. Requires isdttool-pal 1.1.2.
- Backoff when the bridge is unreachable: 30 s, 1 min, 2 min, then every 5 min.
- Diagnostics.
