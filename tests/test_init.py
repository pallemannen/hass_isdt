"""Setting up a charger: devices, entities, and areas."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util

from custom_components.isdt.const import DOMAIN

from .conftest import INFO


@pytest.mark.usefixtures("mock_charger")
async def test_setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The charger, and a device for each slot under it, with their entities."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    device_registry = dr.async_get(hass)
    charger = device_registry.async_get_device_by_identifier(
        (DOMAIN, INFO.serial), config_entry.entry_id
    )
    assert charger is not None
    assert charger.model == "N24"
    assert charger.model_id == "260731091001"
    assert charger.hw_version == "1.0.0.1 (built 2026-07-31)"
    slots = [
        device
        for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
        if device.via_device_id == charger.id
    ]
    assert len(slots) == 24

    entities = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    platforms = {entity.domain for entity in entities}
    assert platforms == {"binary_sensor", "event", "sensor"}
    assert len([e for e in entities if e.domain == "binary_sensor"]) == 24 * 3

    assert hass.states.get("sensor.n24_slots").state == "24"
    total = sum(
        int(hass.states.get(f"sensor.n24_{name}").state)
        for name in (
            "free_slots",
            "cells_charging",
            "cells_charged",
            "invalid_cells",
            "rejected_cells",
        )
    )
    assert total == 24
    assert float(hass.states.get("sensor.n24_total_current").state) > 0
    assert hass.states.get("binary_sensor.n24_slot_06_cell_inserted").state == "on"

    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.usefixtures("mock_charger")
async def test_slots_follow_area(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """The slots are put where the charger is, unless one was put elsewhere on purpose."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    area_registry = ar.async_get(hass)
    garage = area_registry.async_create("Garage")
    office = area_registry.async_create("Office")
    shelf = area_registry.async_create("Shelf")

    device_registry = dr.async_get(hass)
    charger = device_registry.async_get_device_by_identifier(
        (DOMAIN, INFO.serial), config_entry.entry_id
    )
    slots = [
        device
        for device in dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
        if device.via_device_id == charger.id
    ]

    device_registry.async_update_device(charger.id, area_id=garage.id)
    await hass.async_block_till_done()
    assert {device_registry.async_get(slot.id).area_id for slot in slots} == {garage.id}

    # One slot is moved on purpose. It stays when the charger moves.
    device_registry.async_update_device(slots[0].id, area_id=shelf.id)
    device_registry.async_update_device(charger.id, area_id=office.id)
    await hass.async_block_till_done()
    assert device_registry.async_get(slots[0].id).area_id == shelf.id
    assert {device_registry.async_get(slot.id).area_id for slot in slots[1:]} == {office.id}

    assert await hass.config_entries.async_unload(config_entry.entry_id)


def _restored_start(entity_id: str, start: datetime) -> tuple[State, dict]:
    return (
        State(entity_id, start.isoformat()),
        {
            "native_value": {
                "__type": "<class 'datetime.datetime'>",
                "isoformat": start.isoformat(),
            },
            "native_unit_of_measurement": None,
        },
    )


@pytest.mark.usefixtures("mock_charger")
async def test_charging_since_restored(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A cell that finished before Home Assistant started keeps the start of its charge."""
    start = datetime(2026, 11, 3, 20, 0, tzinfo=UTC)
    mock_restore_cache_with_extra_data(
        hass,
        (
            _restored_start("sensor.n24_slot_02_charging_since", start),
            # Later than its charge allows: from another cell, swapped meanwhile.
            _restored_start("sensor.n24_slot_05_charging_since", dt_util.utcnow()),
        ),
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.n24_slot_02_charging_since").state == start.isoformat()
    assert hass.states.get("sensor.n24_slot_05_charging_since").state == "unknown"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
