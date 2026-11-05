"""On/off sensors of each slot, for automations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CATEGORY_INVALID,
    CATEGORY_REJECTED,
    STATUS_CHARGING,
    STATUS_EMPTY,
    STATUS_PRE_CHARGE,
)
from .coordinator import IsdtConfigEntry, IsdtCoordinator, SlotState, slot_category
from .entity import IsdtSlotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IsdtSlotBinarySensorDescription(BinarySensorEntityDescription):
    """An on/off sensor of a slot."""

    value: Callable[[SlotState], bool]


SLOT_BINARY_SENSORS: tuple[IsdtSlotBinarySensorDescription, ...] = (
    IsdtSlotBinarySensorDescription(
        key="cell_inserted",
        value=lambda slot: slot.status != STATUS_EMPTY,
    ),
    IsdtSlotBinarySensorDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value=lambda slot: slot.status in (STATUS_CHARGING, STATUS_PRE_CHARGE),
    ),
    # The cells counted as invalid or rejected by the charger device
    IsdtSlotBinarySensorDescription(
        key="problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda slot: slot_category(slot) in (CATEGORY_INVALID, CATEGORY_REJECTED),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsdtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the on/off sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        IsdtSlotBinarySensor(coordinator, slot, description)
        for slot in coordinator.slots
        for description in SLOT_BINARY_SENSORS
    )


class IsdtSlotBinarySensor(IsdtSlotEntity, BinarySensorEntity):
    """An on/off sensor of one slot."""

    entity_description: IsdtSlotBinarySensorDescription

    def __init__(
        self,
        coordinator: IsdtCoordinator,
        slot: SlotState,
        description: IsdtSlotBinarySensorDescription,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, slot, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Available once the slot has been read."""
        return super().available and bool(self.slot.metrics)

    @property
    def is_on(self) -> bool:
        """Whether it is on."""
        return self.entity_description.value(self.slot)
