"""Charger events: a slot finished, all slots finished, a cell must come out, a charge runs
unusually long."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import EVENT_TYPES
from .coordinator import IsdtConfigEntry, IsdtCoordinator
from .entity import IsdtChargerEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsdtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event entity."""
    async_add_entities([IsdtChargerEvent(entry.runtime_data)])


class IsdtChargerEvent(IsdtChargerEntity, EventEntity):
    """Events of the charger. The slot is in the event's attributes."""

    _attr_event_types = EVENT_TYPES

    def __init__(self, coordinator: IsdtCoordinator) -> None:
        """Set up the entity."""
        super().__init__(coordinator, "charger_event")

    async def async_added_to_hass(self) -> None:
        """Listen for events."""
        await super().async_added_to_hass()
        self.async_on_remove(self.coordinator.async_add_event_listener(self._handle_event))

    @callback
    def _handle_event(self, event_type: str, attributes: dict[str, Any]) -> None:
        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()
