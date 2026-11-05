"""Base entities for the ISDT charger integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IsdtCoordinator, SlotState


def charger_identifier(coordinator: IsdtCoordinator) -> tuple[str, str]:
    """The device registry identifier of the charger."""
    entry = coordinator.config_entry
    return (DOMAIN, entry.unique_id or entry.entry_id)


def slot_identifier(coordinator: IsdtCoordinator, slot: SlotState) -> str:
    """The device registry identifier of a slot."""
    return f"{charger_identifier(coordinator)[1]}_slot_{slot.number:02d}"


class IsdtChargerEntity(CoordinatorEntity[IsdtCoordinator]):
    """An entity of the charger itself."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IsdtCoordinator, key: str) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        identifier = charger_identifier(coordinator)
        self._attr_unique_id = f"{identifier[1]}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={identifier})


class IsdtSlotEntity(CoordinatorEntity[IsdtCoordinator]):
    """An entity of one slot. Each slot is its own device, under the charger."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IsdtCoordinator, slot: SlotState, key: str) -> None:
        """Set up the entity."""
        super().__init__(coordinator)
        self.slot = slot
        slot_id = slot_identifier(coordinator, slot)
        self._attr_unique_id = f"{slot_id}_{key}"
        self._attr_translation_key = key
        # The device itself is created at setup, under the charger.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, slot_id)})
