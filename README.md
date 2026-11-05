# ISDT Charger for Home Assistant

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=Integration&repository=hass_isdt&owner=pallemannen)

Monitors an ISDT battery charger, slot by slot. Developed with the ISDT N24 (24 slots, NiMH and NiCd, AA and AAA); other ISDT chargers that [isdttool](https://github.com/pallemannen/isdttool) supports may work too.

## Tested models

| Model | Connection | Tested by |
|---|---|---|
| N24 (24 slots, NiMH and NiCd, AA and AAA) | USB | Maintainer |
| A4, C4, C4 EVO, Q8 | USB | Not yet. isdttool reads them, but the slot logic is built on what the N24 reports. |

If yours works, or doesn't, please [open an issue](https://github.com/pallemannen/hass_isdt/issues).

The charger is reached through an isdttool bridge, so it can be plugged into any machine on the network, for example a Raspberry Pi next to it. The integration only reads from the charger; it never changes anything on it.

## What you get

The charger is a device, and each slot is a device of its own under it (`N24 Slot 01` to `N24 Slot 24`). Per slot:

| Entity | |
|---|---|
| Status | Empty, idle, pre-charging, charging, charged, rejected |
| Verdict | What to do with the cell, see below |
| Voltage, current | Live values |
| Cell inserted, Charging, Problem | On/off, for automations. Problem is on for invalid and rejected cells, see below. |
| Progress | Estimated charge in percent while charging, 100 when done. A battery level, so battery cards show it. |
| Charged capacity | mAh put into the cell during this charge |
| Charging since | When this charge started |
| Internal resistance | Measured at the start of a charge |
| Temperature | Cell temperature |
| Charge stopped by (diagnostic) | Voltage limit, -ΔV, 0ΔV, or a failed pre-charge |
| Charging time (diagnostic, disabled) | Duration of this charge. It changes with every poll; Charging since tells the same without that. |
| Charger temperature (diagnostic, disabled) | |

Measurements of an empty slot are unavailable, rather than showing the last cell's values.

The slots are put in the charger's area, and move with it. A slot you put in another area yourself stays there.

The charger device has a **Temperature**, the highest of the temperatures the charger measures inside, a **Total current**, what it puts into all cells together, a **Slots** count (24 on the N24), and five counts that always add up to it, since every slot is in exactly one: **Free slots**, **Cells charging** (including pre-charge), **Cells charged** (finished, waiting to be taken out), **Invalid cells** (possibly alkaline, or shorted; the cells that raise a repair), and **Rejected cells** (refused by the charger). It also has a **Charger event** entity that fires:

- `charged`: a slot finished charging.
- `all_charged`: nothing is charging anymore.
- `remove_cell`: a cell must come out (see below).
- `long_charge`: a charge has run for 4 hours.

A cell that is a hazard also raises a repair under **Settings → Repairs**: an alkaline that is being charged, or a shorted cell (errors), and a charge running for more than 4 hours (warning). The repair goes away by itself once the slot is empty, or charging stops.

The slot number, verdict, capacity and so on are in the event's attributes. Use them in automations, for example to send a notification.

### Blueprint

**ISDT charger event** runs your actions when the charger reports an event: all slots charged (the default), a slot charged, a cell that must come out, or an unusually long charge. The actions can use the slot number, the verdict and so on. It only reacts to new events, not to Home Assistant starting or the charger coming back.

[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fpallemannen%2Fhass_isdt%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fcharger_event.yaml)

Blueprints don't come with the integration through HACS; import it with the button, or from `https://github.com/pallemannen/hass_isdt/blob/main/blueprints/automation/charger_event.yaml`.

### Verdict

The verdict is per insertion: the charger can't tell one cell from another, so it starts over whenever a slot is emptied.

| Verdict | Meaning |
|---|---|
| Good | Normal charge, normal internal resistance |
| Worn | Internal resistance at or above the limit (default 400 mΩ, see options). Healthy NiMH cells read about 150–300 mΩ. |
| Rejected | The charger refused the cell. Often an alkaline, or a NiCd. |
| Remove: possibly alkaline | The cell behaves like an alkaline: the charger pre-charges it at a voltage no flat NiMH has, or its internal resistance is 1000 mΩ or more. Take it out; alkalines can leak when charged, and the charger retries them every few hours. Fires `remove_cell`. |
| Trash: shorted | The cell stays at 0 V while being pre-charged. Fires `remove_cell`. |
| Checking | Not enough information yet |

The thresholds come from 85 charges of real cells. Expect to tune the worn limit. Cells need force to come out of the N24, which can briefly disconnect the neighbouring cells; the charger then re-detects them. Cells that already charged normally are not flagged because of that.

The charger only charges, it never discharges, so it can't tell a cell's real capacity. The charged capacity is what went in, not what the cell holds.

## Installation

### 1. The bridge

On the machine the charger is plugged into:

    pip install isdttool-pal
    isdttool list
    isdttool --serial <serial from list> serve

`isdttool serve` runs until the charger is unplugged, so run it as a service. isdttool ships a systemd template, `contrib/isdttool@.service`; see the [isdttool README](https://github.com/pallemannen/isdttool). One bridge serves one charger, on port 24000 by default; give further chargers 24001, 24002, and so on.

The bridge serves one client at a time, and a new client replaces the current one. The integration connects only for the moment it polls, so you can still use `isdttool --host` from the command line in between. For long command line sessions, stop the bridge and use the charger over USB directly.

### 2. The integration

Add this repository to HACS as a custom repository (category: integration), install **ISDT Charger**, and restart Home Assistant. Then go to **Settings → Devices & services → Add integration → ISDT Charger**, and enter the host and port of the bridge.

Options: the poll interval (default 30 seconds), and the internal resistance from which a cell counts as worn. If the charger moves to another machine, use **Reconfigure** to change the address; the entities stay.

If the bridge can't be reached, the integration retries after 30 seconds, 1 minute, 2 minutes, and then every 5 minutes.

## Related projects

- [isdttool](https://github.com/pallemannen/isdttool): talks to ISDT chargers over USB, and is the bridge this integration uses. A fork of [maxried/isdttool](https://github.com/maxried/isdttool).
- [ISDT Air BLE](https://github.com/mtheli/isdt_air_ble) by mtheli: Home Assistant integration for ISDT chargers with Bluetooth, such as the C4 Air and A8 Air.

## Development

The tests replay the raw replies of an N24, logged while it charged 85 real cells. Run them with:

    pip install -r requirements_test.txt
    pytest

## Disclaimer

This is an independent community project. It is not affiliated with, endorsed by, or sponsored by ISDT. All product names and trademarks are the property of their respective owners.
