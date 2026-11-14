# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- A repair, "Check the battery type" (error), when a cell's voltage early in the charge doesn't
  fit the type it is charged as, such as NiMH charged as NiZn. The battery type is one setting for
  all slots, so a new batch is easily charged as the last one.
- NiZn (5) confirmed on the N24. On Auto it rejects NiZn cells: set the type to NiZn by hand.

### Changed
- The N24 reports NiCd (8) when the charger's battery type is set to NiCd (confirmed; on Auto, nickel cells are NiMH).

## [0.3.0] - 2026-11-05

### Added
- Chargers are discovered on the network over mDNS/zeroconf: a bridge running isdttool-pal
  2.1.0 or later advertises itself, and Home Assistant offers the charger to set up without
  asking for its address. A charger already set up keeps working, and a bridge that moved to a
  new address is followed.

### Changed
- Requires isdttool-pal 2.1.0, whose bridge advertises itself. Update the bridge
  (`isdttool serve`) to 2.1.0 too.

## [0.2.0] - 2026-11-05

### Added
- Per slot: **Cell inserted**, **Charging** and **Problem** on/off sensors. Problem is on for invalid and rejected cells.
- Per slot: **Charging since**, when the current charge started. A cell that finished before a restart keeps it.
- Per slot: **Battery type**, as chosen for the slot on the charger. Only NiMH has been seen on the N24; the other types use the codes of the ISDT C4.
- Charger: **Total current**, what the charger puts into all cells together.
- The slots are put in the charger's area, and move with it. A slot put in another area on purpose stays there.
- Blueprint **ISDT charger event**: runs actions on a charger event, all slots charged by default.
- Tests, replaying the logged replies of an N24 during 85 charges of real cells. They run on GitHub.
- README: tested models, related projects, disclaimer.

### Changed
- Requires isdttool-pal 2.0.0, whose bridge carries packets instead of USB reports. Update the bridge (`isdttool serve`) to 2.0.0 too, at the same time.
- Progress is a battery level, so it gets battery icons and works with battery cards.
- The alkaline and worn checks only apply to nickel cells, or cells of unknown type. A pre-charge counts as possibly alkaline between 1.3 and 2.3 V, no longer at any voltage from 1.3 V, so a flat lithium cell isn't taken for an alkaline.
- A completed charge counts for every battery type, not only NiMH, so `charged` and `all_charged` fire for lithium cells too.
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
