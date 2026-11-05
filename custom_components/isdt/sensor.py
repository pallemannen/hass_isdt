"""Sensors for the ISDT charger integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    REMOVE_VERDICTS,
    STATUS_CHARGED,
    STATUS_CHARGING,
    STATUS_EMPTY,
    STATUS_PRE_CHARGE,
    STATUSES,
    TERMINATION_UNKNOWN,
    TERMINATIONS,
    VERDICTS,
)
from .coordinator import IsdtConfigEntry, IsdtCoordinator, SlotState
from .entity import IsdtChargerEntity, IsdtSlotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IsdtSlotSensorDescription(SensorEntityDescription):
    """A slot sensor."""

    value: Callable[[SlotState], Any]
    # Measurements of an empty slot are left over from the last cell, so they are hidden.
    needs_cell: bool = True
    # Only meaningful once charging has finished
    needs_charged: bool = False


def _metric(key: str, scale: float = 1) -> Callable[[SlotState], Any]:
    return lambda slot: slot.metrics[key] / scale if scale != 1 else slot.metrics[key]


SLOT_SENSORS: tuple[IsdtSlotSensorDescription, ...] = (
    IsdtSlotSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUSES,
        value=lambda slot: slot.status,
        needs_cell=False,
    ),
    IsdtSlotSensorDescription(
        key="verdict",
        device_class=SensorDeviceClass.ENUM,
        options=VERDICTS,
        value=lambda slot: slot.verdict,
    ),
    IsdtSlotSensorDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=3,
        value=_metric("charging voltage", 1000),
    ),
    IsdtSlotSensorDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=3,
        value=_metric("charging current", 1000),
    ),
    IsdtSlotSensorDescription(
        key="progress",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value=_metric("progress"),
    ),
    IsdtSlotSensorDescription(
        key="charged_capacity",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mAh",
        value=_metric("capacity or peak voltage"),
    ),
    IsdtSlotSensorDescription(
        key="charging_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        value=_metric("time"),
    ),
    IsdtSlotSensorDescription(
        key="resistance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mΩ",
        value=lambda slot: slot.resistance,
    ),
    IsdtSlotSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=_metric("temperature"),
    ),
    IsdtSlotSensorDescription(
        key="termination",
        device_class=SensorDeviceClass.ENUM,
        options=[*TERMINATIONS.values(), TERMINATION_UNKNOWN],
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda slot: slot.termination,
        needs_charged=True,
    ),
    IsdtSlotSensorDescription(
        key="internal_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=_metric("internal_temperature"),
        needs_cell=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IsdtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        IsdtChargerSensor(coordinator, description) for description in CHARGER_SENSORS
    ]
    entities.extend(
        IsdtSlotSensor(coordinator, slot, description)
        for slot in coordinator.slots
        for description in SLOT_SENSORS
    )
    async_add_entities(entities)


class IsdtSlotSensor(IsdtSlotEntity, SensorEntity):
    """A measurement, or state, of one slot."""

    entity_description: IsdtSlotSensorDescription

    def __init__(
        self,
        coordinator: IsdtCoordinator,
        slot: SlotState,
        description: IsdtSlotSensorDescription,
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, slot, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Hide what doesn't apply to the slot right now."""
        if not super().available or not self.slot.metrics:
            return False
        if self.entity_description.needs_cell and self.slot.status == STATUS_EMPTY:
            return False
        if self.entity_description.needs_charged and self.slot.status != STATUS_CHARGED:
            return False
        return True

    @property
    def native_value(self) -> Any:
        """The value."""
        return self.entity_description.value(self.slot)


@dataclass(frozen=True, kw_only=True)
class IsdtChargerSensorDescription(SensorEntityDescription):
    """A count over all slots of the charger."""

    value: Callable[[list[SlotState]], int]


CHARGER_SENSORS: tuple[IsdtChargerSensorDescription, ...] = (
    IsdtChargerSensorDescription(
        key="slots",
        value=len,
    ),
    IsdtChargerSensorDescription(
        key="free_slots",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda slots: sum(slot.status == STATUS_EMPTY for slot in slots),
    ),
    IsdtChargerSensorDescription(
        key="cells_charging",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda slots: sum(
            slot.status in (STATUS_CHARGING, STATUS_PRE_CHARGE) for slot in slots
        ),
    ),
    IsdtChargerSensorDescription(
        key="cells_charged",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda slots: sum(slot.status == STATUS_CHARGED for slot in slots),
    ),
    IsdtChargerSensorDescription(
        key="hazardous_cells",
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda slots: sum(slot.verdict in REMOVE_VERDICTS for slot in slots),
    ),
)


class IsdtChargerSensor(IsdtChargerEntity, SensorEntity):
    """A count over all slots of the charger."""

    entity_description: IsdtChargerSensorDescription

    def __init__(
        self, coordinator: IsdtCoordinator, description: IsdtChargerSensorDescription
    ) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> int:
        """The count."""
        return self.entity_description.value(self.coordinator.slots)
