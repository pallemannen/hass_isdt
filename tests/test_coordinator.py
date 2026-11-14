"""The slot logic, replayed against two logged batches of real cells."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.isdt.const import DOMAIN
from custom_components.isdt.coordinator import IsdtCoordinator, SlotState, slot_category

from .conftest import INFO
from .replay import load_polls

CATEGORIES = {"free", "charging", "charged", "invalid", "rejected"}


async def _replay(
    hass: HomeAssistant, config_entry: MockConfigEntry, name: str
) -> tuple[IsdtCoordinator, list[tuple[str, Any]], set[str]]:
    """Replay a batch. Returns the coordinator, the events, and every repair raised."""
    config_entry.add_to_hass(hass)
    coordinator = IsdtCoordinator(hass, config_entry, INFO)
    events: list[tuple[str, Any]] = []
    coordinator.async_add_event_listener(
        lambda event_type, attributes: events.append(
            (event_type, attributes.get("slot", attributes.get("charged_slots")))
        )
    )
    issue_registry = ir.async_get(hass)
    raised: set[str] = set()
    for now, metrics in load_polls(name):
        coordinator._process(metrics, now)
        coordinator._first = False
        coordinator._sync_repairs()
        # Every slot is in exactly one of the charger's counts.
        categories = Counter(slot_category(slot) for slot in coordinator.slots)
        assert set(categories) <= CATEGORIES
        assert categories.total() == INFO.channels
        raised |= {
            issue.issue_id.removeprefix(f"{config_entry.entry_id}_")
            for issue in issue_registry.issues.values()
            if issue.domain == DOMAIN
        }
    return coordinator, events, raised


def _of(events: list[tuple[str, Any]], event_type: str) -> list[Any]:
    return [slot for kind, slot in events if kind == event_type]


async def test_batch1(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Batch 1: AA cells, two alkalines among them."""
    _, events, raised = await _replay(hass, config_entry, "batch1.log.gz")

    # The alkaline in slot 10 was already flagged when the log starts, so it raises a repair,
    # but no event.
    assert _of(events, "remove_cell") == [22]
    assert raised == {"slot_10_possible_alkaline", "slot_22_possible_alkaline"}
    assert len(_of(events, "charged")) == 11
    assert len(_of(events, "all_charged")) == 2


async def test_batch2(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Batch 2 and 3: AAA cells, with alkalines, and a shorted cell in slot 3."""
    _, events, raised = await _replay(hass, config_entry, "batch2.log.gz")

    assert _of(events, "remove_cell") == [6, 1, 4, 12, 15, 3]
    assert raised == {
        "slot_10_possible_alkaline",
        "slot_06_possible_alkaline",
        "slot_01_possible_alkaline",
        "slot_04_possible_alkaline",
        "slot_12_possible_alkaline",
        "slot_15_possible_alkaline",
        "slot_03_shorted",
    }
    assert len(_of(events, "charged")) == 44
    assert len(_of(events, "all_charged")) == 3
    # Every hazard was taken out in the end, so no repair is left.
    assert not [
        issue for issue in ir.async_get(hass).issues.values() if issue.domain == DOMAIN
    ]


async def test_charge_start_is_steady(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The start of a charge doesn't move from poll to poll."""
    config_entry.add_to_hass(hass)
    coordinator = IsdtCoordinator(hass, config_entry, INFO)
    starts: dict[int, set] = {}
    for now, metrics in load_polls("batch1.log.gz"):
        coordinator._process(metrics, now)
        coordinator._first = False
        for slot in coordinator.slots:
            if slot.charge_start is not None:
                starts.setdefault(slot.number, set()).add(slot.charge_start)

    # One start per charge. The alkaline in slot 10 is retried by the charger every hour or
    # two, and each retry is a new charge.
    assert {number: len(found) for number, found in starts.items() if number != 10} == {
        number: 1 for number in starts if number != 10
    }
    assert len(starts[10]) > 1


async def test_lithium(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """A Li-ion cell is not taken for an alkaline, and its completed charge counts.

    Built from an empty slot of a logged poll. The codes are those of the ISDT C4, which the
    N24 most likely shares: 4 while pre-charging, 2 for Li-ion.
    """
    config_entry.add_to_hass(hass)
    coordinator = IsdtCoordinator(hass, config_entry, INFO)
    events: list[str] = []
    coordinator.async_add_event_listener(lambda event_type, _: events.append(event_type))
    now, metrics = load_polls("batch1.log.gz")[894]
    empty = next(m for m in metrics if m["dimensions id"] == 4)
    number = empty["channel"] + 1
    coordinator._process(metrics, now)
    coordinator._first = False

    def poll(minutes: int, **values: int) -> SlotState:
        metrics[number - 1] = {**empty, "dimensions id": 1, "resistance": 0, **values}
        coordinator._process(metrics, now + timedelta(minutes=minutes))
        return coordinator.slots[number - 1]

    # Flat, so pre-charged first: no type is reported yet.
    slot = poll(1, **{"mode id": 3, "chemistry id": 4, "charging voltage": 2900,
                      "charging current": 100, "progress": 1, "time": 60})
    assert slot.verdict == "checking"
    assert slot.battery_type is None
    slot = poll(10, **{"mode id": 3, "chemistry id": 2, "charging voltage": 3700,
                       "charging current": 1000, "progress": 40, "time": 600,
                       "resistance": 450})
    assert slot.battery_type == "li_ion"
    # Worn is judged by nickel standards, so it doesn't apply.
    assert slot.verdict == "good"
    slot = poll(60, **{"mode id": 4, "chemistry id": 2, "charging voltage": 4200,
                       "charging current": 0, "progress": 1, "time": 3600,
                       "resistance": 450})
    assert slot.status == "charged"
    assert "charged" in events
    assert "remove_cell" not in events


async def test_wrong_battery_type(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """A cell whose voltage doesn't fit the type it is charged as raises a repair.

    NiZn cells set to NiZn charged at about 1.75 V (2026-11-13); a NiMH cell charged as NiZn reads
    well under that.
    """
    config_entry.add_to_hass(hass)
    coordinator = IsdtCoordinator(hass, config_entry, INFO)
    # A copy: the polls are shared between tests.
    now, polled = load_polls("batch1.log.gz")[894]
    metrics = [dict(m) for m in polled]
    empty = {**metrics[0], "dimensions id": 4, "mode id": 0, "chemistry id": 0,
             "charging voltage": 0, "charging current": 0, "resistance": 0, "time": 0}
    number = 1
    metrics[0] = empty
    coordinator._process(metrics, now)
    coordinator._first = False
    issue_id = f"{config_entry.entry_id}_slot_{number:02d}_wrong_type"

    def poll(minutes: int, **values: int) -> bool:
        metrics[number - 1] = {**empty, **values}
        coordinator._process(metrics, now + timedelta(minutes=minutes))
        coordinator._sync_repairs()
        return ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    charging = {"dimensions id": 1, "mode id": 3, "chemistry id": 5, "charging current": 1000,
                "progress": 90, "time": 60, "resistance": 200}
    assert not poll(1, **charging, **{"charging voltage": 1750})
    assert coordinator.slots[number - 1].battery_type == "nizn"
    assert not poll(2)  # emptied
    assert poll(3, **charging, **{"charging voltage": 1380})
    assert not poll(4)  # emptied: the repair goes
