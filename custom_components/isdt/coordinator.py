"""Polls the charger, and keeps track of each slot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, ChargerInfo, read_metrics
from .const import (
    REPAIR_WRONG_TYPE,
    TYPE_CHARGE_VOLTAGE,
    TYPE_CHECK_WINDOW,
    TYPE_NAMES,
    ALKALINE_FLAT_VOLTAGE,
    ALKALINE_PRECHARGE_VOLTAGE,
    ALKALINE_RESISTANCE,
    BACKOFF_INTERVALS,
    BATTERY_TYPES,
    CATEGORY_CHARGED,
    CATEGORY_CHARGING,
    CATEGORY_FREE,
    CATEGORY_INVALID,
    CATEGORY_REJECTED,
    CHARGE_START_TOLERANCE,
    CHEMISTRY_PRE_CHARGE_OR_REJECTED,
    CHEMISTRY_PRE_CHARGE,
    CHEMISTRY_REJECTED,
    CONF_WORN_RESISTANCE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WORN_RESISTANCE,
    DIMENSIONS_EMPTY,
    DOMAIN,
    EVENT_ALL_CHARGED,
    EVENT_CHARGED,
    EVENT_LONG_CHARGE,
    EVENT_REMOVE_CELL,
    LONG_CHARGE,
    MIN_RESISTANCE,
    MODE_CHARGED,
    MODE_CHARGING,
    MODE_IDLE,
    NICKEL_TYPES,
    PRE_CHARGE_CURRENT,
    REMOVE_VERDICTS,
    REPAIR_LONG_CHARGE,
    REPAIR_POSSIBLE_ALKALINE,
    REPAIR_SEVERITY,
    REPAIR_SHORTED,
    SHORTED_DURATION,
    SHORTED_VOLTAGE,
    STATUS_CHARGED,
    STATUS_CHARGING,
    STATUS_EMPTY,
    STATUS_IDLE,
    STATUS_PRE_CHARGE,
    STATUS_REJECTED,
    STATUS_UNKNOWN,
    TERMINATION_UNKNOWN,
    TERMINATIONS,
    VERDICT_CHECKING,
    VERDICT_GOOD,
    VERDICT_POSSIBLE_ALKALINE,
    VERDICT_REJECTED,
    VERDICT_SHORTED,
    VERDICT_WORN,
)

_LOGGER = logging.getLogger(__name__)

type IsdtConfigEntry = ConfigEntry[IsdtCoordinator]


def slot_status(metrics: dict[str, Any]) -> str:
    """The status of a slot, from its metrics."""
    if metrics["dimensions id"] == DIMENSIONS_EMPTY:
        return STATUS_EMPTY
    mode = metrics["mode id"]
    chemistry = metrics["chemistry id"]
    if mode == MODE_CHARGING:
        if chemistry == CHEMISTRY_PRE_CHARGE or (
            metrics["progress"] <= 1 and 0 < metrics["charging current"] < PRE_CHARGE_CURRENT
        ):
            return STATUS_PRE_CHARGE
        return STATUS_CHARGING
    if mode == MODE_CHARGED:
        return STATUS_REJECTED if chemistry == CHEMISTRY_REJECTED else STATUS_CHARGED
    if mode == MODE_IDLE:
        return STATUS_IDLE
    return STATUS_UNKNOWN


def slot_category(slot: SlotState) -> str:
    """Which of the charger's counts a slot belongs to. Every slot is in exactly one."""
    if slot.status == STATUS_EMPTY:
        return CATEGORY_FREE
    if slot.verdict in REMOVE_VERDICTS:
        return CATEGORY_INVALID
    if slot.verdict == VERDICT_REJECTED:
        return CATEGORY_REJECTED
    if slot.status in (STATUS_CHARGED, STATUS_REJECTED):
        # Rejected after it charged normally: it was only bumped, and is full.
        return CATEGORY_CHARGED
    # Charging, pre-charging, or about to start
    return CATEGORY_CHARGING


@dataclass
class SlotState:
    """What is known about the cell in one slot, since it was inserted.

    The charger doesn't know one cell from another, so everything here is per insertion: it
    starts over when the slot is emptied.
    """

    number: int  # 1-based, as printed on the charger
    metrics: dict[str, Any] = field(default_factory=dict)
    status: str = STATUS_EMPTY
    verdict: str | None = None
    termination: str | None = None
    resistance: int | None = None  # Last measured internal resistance, mΩ
    battery_type: str | None = None  # Last reported, see BATTERY_TYPES
    charged_normally: bool = False  # Completed a normal charge since insertion
    flat_since: datetime | None = None
    charge_start: datetime | None = None
    remove_reported: bool = False
    long_charge_reported: bool = False
    start_voltage: int | None = None  # mV, early in the first charge since insertion

    def reset(self) -> None:
        """The slot was emptied."""
        self.verdict = None
        self.termination = None
        self.resistance = None
        self.battery_type = None
        self.charged_normally = False
        self.flat_since = None
        self.charge_start = None
        self.remove_reported = False
        self.long_charge_reported = False
        self.start_voltage = None

    def mismatched_type(self) -> bool:
        """Charging as a type whose voltage the cell clearly doesn't have."""
        expected = TYPE_CHARGE_VOLTAGE.get(self.battery_type or "")
        return (
            expected is not None
            and self.start_voltage is not None
            and self.status in (STATUS_CHARGING, STATUS_CHARGED)
            and not expected[0] <= self.start_voltage <= expected[1]
        )


class IsdtCoordinator(DataUpdateCoordinator[list[SlotState]]):
    """Polls all slots of one charger."""

    config_entry: IsdtConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: IsdtConfigEntry, info: ChargerInfo
    ) -> None:
        """Set up the coordinator."""
        self.interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=self.interval,
        )
        self.info = info
        self.host: str = entry.data[CONF_HOST]
        self.port: int = entry.data[CONF_PORT]
        self.worn_resistance: int = entry.options.get(
            CONF_WORN_RESISTANCE, DEFAULT_WORN_RESISTANCE
        )
        self.slots = [SlotState(number=i + 1) for i in range(info.channels)]
        self._failures = 0
        self._first = True
        self._charged_since_all = False
        self._event_listeners: list[Callable[[str, dict[str, Any]], None]] = []

    @callback
    def async_add_event_listener(
        self, listener: Callable[[str, dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Listen for charger events. Returns a function that removes the listener."""
        self._event_listeners.append(listener)
        return lambda: self._event_listeners.remove(listener)

    def _fire(self, event_type: str, attributes: dict[str, Any]) -> None:
        _LOGGER.debug("%s: %s %s", self.name, event_type, attributes)
        for listener in list(self._event_listeners):
            listener(event_type, attributes)

    async def _async_update_data(self) -> list[SlotState]:
        try:
            metrics = await self.hass.async_add_executor_job(
                read_metrics, self.host, self.port, self.info.model, self.info.channels
            )
        except CannotConnect as err:
            # Home Assistant logs only the first failure in a row. This logs all of them.
            _LOGGER.debug("%s: poll failed: %s", self.name, err)
            # Back off: 30 s, 1 min, 2 min, then every 5 minutes.
            self.update_interval = BACKOFF_INTERVALS[
                min(self._failures, len(BACKOFF_INTERVALS) - 1)
            ]
            self._failures += 1
            raise UpdateFailed(f"Cannot read the charger: {err}") from err

        self._failures = 0
        self.update_interval = self.interval
        self._process(metrics, dt_util.utcnow())
        self._first = False
        self._sync_repairs()
        return self.slots

    def _issue_id(self, kind: str, slot: SlotState) -> str:
        return f"{self.config_entry.entry_id}_slot_{slot.number:02d}_{kind}"

    def _sync_repairs(self) -> None:
        """Raise a repair for each cell that is a hazard, and withdraw it once it is gone.

        Runs after every poll, so issues left over from before a restart are withdrawn, or
        kept, according to what is in the charger now.
        """
        for slot in self.slots:
            wanted = {
                REPAIR_POSSIBLE_ALKALINE: slot.verdict == VERDICT_POSSIBLE_ALKALINE,
                REPAIR_SHORTED: slot.verdict == VERDICT_SHORTED,
                # A cell to take out says so already.
                REPAIR_WRONG_TYPE: slot.mismatched_type() and slot.verdict not in REMOVE_VERDICTS,
                REPAIR_LONG_CHARGE: slot.status in (STATUS_CHARGING, STATUS_PRE_CHARGE)
                and timedelta(seconds=slot.metrics["time"]) >= LONG_CHARGE
                and slot.verdict not in REMOVE_VERDICTS,
            }
            for kind, raise_it in wanted.items():
                issue_id = self._issue_id(kind, slot)
                if raise_it:
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        issue_id,
                        is_fixable=False,
                        is_persistent=False,
                        severity=ir.IssueSeverity(REPAIR_SEVERITY[kind]),
                        translation_key=kind,
                        translation_placeholders={
                            "charger": self.config_entry.title,
                            "slot": str(slot.number),
                            "type": TYPE_NAMES.get(slot.battery_type or "", "?"),
                            "voltage": f"{(slot.start_voltage or slot.metrics.get('charging voltage', 0)) / 1000:.2f}",
                        },
                    )
                else:
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id)


    def _process(self, all_metrics: list[dict[str, Any]], now: datetime) -> None:

        for slot, metrics in zip(self.slots, all_metrics, strict=True):
            previous = slot.status
            status = slot_status(metrics)
            slot.metrics = metrics
            slot.status = status

            if status == STATUS_EMPTY:
                slot.reset()
                continue

            # Only taken while the charger works on the cell: before that, the slot still
            # reports the type of the cell before.
            chemistry = metrics["chemistry id"]
            if status not in (STATUS_CHARGING, STATUS_CHARGED):
                pass
            elif chemistry in BATTERY_TYPES:
                slot.battery_type = BATTERY_TYPES[chemistry]
            elif chemistry not in CHEMISTRY_PRE_CHARGE_OR_REJECTED:
                _LOGGER.debug(
                    "%s: slot %d reports battery type %s, never seen before",
                    self.name,
                    slot.number,
                    chemistry,
                )

            # After a bump, a cell that already charged is pre-charged again, and the
            # resistance it reports then is nonsense (seen: 29 and 5208 mΩ).
            if metrics["resistance"] >= MIN_RESISTANCE and not (
                status == STATUS_PRE_CHARGE and slot.charged_normally
            ):
                slot.resistance = metrics["resistance"]

            first_completion = False

            if status == STATUS_CHARGED:
                slot.termination = TERMINATIONS.get(
                    metrics.get("termination id"), TERMINATION_UNKNOWN
                )
                if (
                    not slot.charged_normally
                    and metrics["chemistry id"] in BATTERY_TYPES
                    and (slot.resistance is None or slot.resistance < ALKALINE_RESISTANCE)
                ):
                    slot.charged_normally = True
                    first_completion = True
            elif status in (STATUS_CHARGING, STATUS_PRE_CHARGE):
                slot.termination = None
                self._track_charge_start(slot, metrics, now)
            if (
                status == STATUS_CHARGING
                and slot.start_voltage is None
                and not slot.charged_normally
                and timedelta(seconds=metrics["time"]) <= TYPE_CHECK_WINDOW
            ):
                slot.start_voltage = metrics["charging voltage"]

            slot.verdict = self._verdict(slot, metrics, status, now)

            if self._first:
                # Nothing is known about what happened before Home Assistant started.
                slot.remove_reported = slot.verdict in REMOVE_VERDICTS
                slot.long_charge_reported = status == STATUS_CHARGING
                continue

            attributes = self._event_attributes(slot)
            # Only the first completed charge per insertion counts. A bumped cell is charged
            # again briefly, and that is not news.
            if first_completion and previous in (STATUS_CHARGING, STATUS_PRE_CHARGE):
                self._charged_since_all = True
                self._fire(EVENT_CHARGED, attributes)
            if slot.verdict in REMOVE_VERDICTS and not slot.remove_reported:
                slot.remove_reported = True
                self._fire(EVENT_REMOVE_CELL, attributes)
            if (
                status in (STATUS_CHARGING, STATUS_PRE_CHARGE)
                and timedelta(seconds=metrics["time"]) >= LONG_CHARGE
                and not slot.long_charge_reported
            ):
                slot.long_charge_reported = True
                self._fire(EVENT_LONG_CHARGE, attributes)

        # A cell that has to come out may pre-charge forever. It doesn't hold up the rest.
        is_charging = any(
            slot.status in (STATUS_CHARGING, STATUS_PRE_CHARGE)
            and slot.verdict not in REMOVE_VERDICTS
            for slot in self.slots
        )
        if self._charged_since_all and not is_charging:
            self._charged_since_all = False
            self._fire(
                EVENT_ALL_CHARGED,
                {
                    "charged_slots": [
                        slot.number for slot in self.slots if slot.status == STATUS_CHARGED
                    ]
                },
            )

    @staticmethod
    def _track_charge_start(slot: SlotState, metrics: dict[str, Any], now: datetime) -> None:
        """When the current charge started, from how long it has been running.

        Each poll gives a slightly different start, as the poll itself takes time, so the start
        only moves when the charger starts over. A cell that already charged normally was only
        bumped, and keeps the start of its real charge.
        """
        start = (now - timedelta(seconds=metrics["time"])).replace(microsecond=0)
        if slot.charge_start is None or (
            not slot.charged_normally
            and abs(start - slot.charge_start) > CHARGE_START_TOLERANCE
        ):
            slot.charge_start = start

    def _verdict(
        self, slot: SlotState, metrics: dict[str, Any], status: str, now: datetime
    ) -> str:
        # A cell that has to come out stays flagged until the slot is emptied.
        if slot.verdict in REMOVE_VERDICTS:
            return slot.verdict

        voltage = metrics["charging voltage"]

        if status == STATUS_PRE_CHARGE:
            if voltage < SHORTED_VOLTAGE:
                if slot.flat_since is None:
                    slot.flat_since = now
                elif now - slot.flat_since >= SHORTED_DURATION:
                    return VERDICT_SHORTED
            else:
                slot.flat_since = None

            # A cell that already charged normally was only bumped, and re-detected.
            if not slot.charged_normally and self._may_be_alkaline(slot) and (
                ALKALINE_PRECHARGE_VOLTAGE[0] <= voltage < ALKALINE_PRECHARGE_VOLTAGE[1]
                or (
                    ALKALINE_FLAT_VOLTAGE[0] <= voltage < ALKALINE_FLAT_VOLTAGE[1]
                    and (slot.resistance or 0) >= ALKALINE_RESISTANCE
                )
            ):
                return VERDICT_POSSIBLE_ALKALINE
        else:
            slot.flat_since = None

        # No healthy NiMH comes close to this. Alkalines do, whether the charger stops after a
        # short pulse, or refuses them right away.
        if (
            not slot.charged_normally
            and self._may_be_alkaline(slot)
            and (slot.resistance or 0) >= ALKALINE_RESISTANCE
        ):
            return VERDICT_POSSIBLE_ALKALINE

        if status == STATUS_REJECTED and not slot.charged_normally:
            return VERDICT_REJECTED

        if slot.resistance is None:
            return VERDICT_CHECKING
        if slot.resistance >= self.worn_resistance and self._may_be_alkaline(slot):
            return VERDICT_WORN
        return VERDICT_GOOD

    @staticmethod
    def _may_be_alkaline(slot: SlotState) -> bool:
        """Whether the nickel checks apply: the cell is a nickel cell, or its type unknown."""
        return slot.battery_type is None or slot.battery_type in NICKEL_TYPES

    @staticmethod
    def _event_attributes(slot: SlotState) -> dict[str, Any]:
        metrics = slot.metrics
        return {
            "slot": slot.number,
            "verdict": slot.verdict,
            "termination": slot.termination,
            "capacity": metrics.get("capacity or peak voltage"),
            "resistance": slot.resistance,
            "voltage": metrics.get("charging voltage", 0) / 1000,
            "charging_time": metrics.get("time"),
        }
