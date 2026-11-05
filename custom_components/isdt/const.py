"""Constants for the ISDT charger integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "isdt"

DEFAULT_PORT = 24000
DEFAULT_SCAN_INTERVAL = 30  # seconds
MIN_SCAN_INTERVAL = 10

# After a failed poll, wait longer and longer before the next try, up to 5 minutes.
BACKOFF_INTERVALS = (
    timedelta(seconds=30),
    timedelta(minutes=1),
    timedelta(minutes=2),
    timedelta(minutes=5),
)

CONF_WORN_RESISTANCE = "worn_resistance"
DEFAULT_WORN_RESISTANCE = 400  # mΩ. Healthy NiMH cells read about 150-300 mΩ on the N24.

# A cell that stays this flat for this long while being pre-charged is shorted.
SHORTED_VOLTAGE = 100  # mV
SHORTED_DURATION = timedelta(minutes=10)

# An alkaline cell that the charger mistakes for a rechargeable shows up as a pre-charge at a
# voltage no flat NiMH has, or as a nearly flat cell with a very high resistance. Under the
# pre-charge current, alkalines were seen at up to 1.97 V. A lithium cell is pre-charged when it
# is flat, at 2.5 V or more; one below 2.3 V is over-discharged, and better taken out, too.
ALKALINE_PRECHARGE_VOLTAGE = (1300, 2300)  # mV
ALKALINE_FLAT_VOLTAGE = (300, 1000)  # mV
ALKALINE_RESISTANCE = 1000  # mΩ

LONG_CHARGE = timedelta(hours=4)

# The start of a charge is worked out from how long it has run. A start that differs more than
# this from the one already known means the charger started over.
CHARGE_START_TOLERANCE = timedelta(minutes=1)

# Lower resistances are measurement glitches. Even a new NiMH cell reads over 100 mΩ.
MIN_RESISTANCE = 50  # mΩ

# Values reported by isdttool for the N24. See the isdttool N24 support for how they were found.
MODE_IDLE = 0
MODE_CHARGING = 3
MODE_CHARGED = 4
CHEMISTRY_PRE_CHARGE = 4
CHEMISTRY_REJECTED = 6
CHEMISTRY_NIMH = 9
CHEMISTRY_PRE_CHARGE_OR_REJECTED = (CHEMISTRY_PRE_CHARGE, CHEMISTRY_REJECTED)

# The battery type, as chosen for the slot on the charger, or detected with Auto. The N24 has
# only been seen to report NiMH (9) while charging. The other codes are those of the ISDT C4,
# which uses the same field; they are likely, but not confirmed for the N24. While pre-charging
# (4) or after rejecting a cell (6), the charger doesn't report the type.
BATTERY_TYPES = {
    0: "auto",
    1: "lihv",
    2: "li_ion",
    3: "life",
    5: "nizn",
    8: "nicd",
    9: "nimh",
}
# The alkaline, and worn, checks are made for nickel cells. They also apply while the type is
# not known, or Auto, as an alkaline is reported as a nickel cell, or not at all.
NICKEL_TYPES = ("auto", "nicd", "nimh")
DIMENSIONS_EMPTY = 4
PRE_CHARGE_CURRENT = 200  # mA. Pre-charge runs at about 100 mA, normal charging at about 1 A.

# Slot status
STATUS_EMPTY = "empty"
STATUS_IDLE = "idle"
STATUS_PRE_CHARGE = "pre_charge"
STATUS_CHARGING = "charging"
STATUS_CHARGED = "charged"
STATUS_REJECTED = "rejected"
STATUS_UNKNOWN = "unknown"
STATUSES = [
    STATUS_EMPTY,
    STATUS_IDLE,
    STATUS_PRE_CHARGE,
    STATUS_CHARGING,
    STATUS_CHARGED,
    STATUS_REJECTED,
    STATUS_UNKNOWN,
]

# Verdict about the cell in a slot, per insertion
VERDICT_CHECKING = "checking"
VERDICT_GOOD = "good"
VERDICT_WORN = "worn"
VERDICT_REJECTED = "rejected"
VERDICT_POSSIBLE_ALKALINE = "possible_alkaline"
VERDICT_SHORTED = "shorted"
VERDICTS = [
    VERDICT_CHECKING,
    VERDICT_GOOD,
    VERDICT_WORN,
    VERDICT_REJECTED,
    VERDICT_POSSIBLE_ALKALINE,
    VERDICT_SHORTED,
]
# Verdicts that mean "take this cell out", and stay until the slot is emptied.
REMOVE_VERDICTS = (VERDICT_POSSIBLE_ALKALINE, VERDICT_SHORTED)

# The charger's counts. Every slot is in exactly one, so they add up to the number of slots.
CATEGORY_FREE = "free"
CATEGORY_CHARGING = "charging"
CATEGORY_CHARGED = "charged"
CATEGORY_INVALID = "invalid"  # Possibly alkaline, or shorted: the cells that raise a repair
CATEGORY_REJECTED = "rejected"  # Refused by the charger

# Why charging stopped
TERMINATIONS = {
    1: "voltage_limit",
    2: "minus_delta_v",
    5: "zero_delta_v",
    8: "pre_charge_failed",
}
TERMINATION_UNKNOWN = "unknown"

# Charger events
EVENT_CHARGED = "charged"
EVENT_ALL_CHARGED = "all_charged"
EVENT_REMOVE_CELL = "remove_cell"
EVENT_LONG_CHARGE = "long_charge"
EVENT_TYPES = [EVENT_CHARGED, EVENT_ALL_CHARGED, EVENT_REMOVE_CELL, EVENT_LONG_CHARGE]

# Repairs, raised while a hazardous cell is in a slot
REPAIR_POSSIBLE_ALKALINE = "possible_alkaline"
REPAIR_SHORTED = "shorted"
REPAIR_LONG_CHARGE = "long_charge"
REPAIR_SEVERITY = {
    # Alkalines can leak, or burst, when charged.
    REPAIR_POSSIBLE_ALKALINE: "error",
    # A shorted cell takes current, and turns it into heat.
    REPAIR_SHORTED: "error",
    REPAIR_LONG_CHARGE: "warning",
}
