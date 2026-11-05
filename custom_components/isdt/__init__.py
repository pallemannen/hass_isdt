"""The ISDT charger integration.

Talks to an ISDT charger through an isdttool bridge (`isdttool serve`) on the network. The
charger itself can be plugged into any machine that runs the bridge.
"""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.event import async_track_device_registry_updated_event

from .api import CannotConnect, get_info
from .const import DOMAIN
from .coordinator import IsdtConfigEntry, IsdtCoordinator
from .entity import slot_identifier

PLATFORMS = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: IsdtConfigEntry) -> bool:
    """Set up a charger."""
    try:
        info = await hass.async_add_executor_job(
            get_info, entry.data[CONF_HOST], entry.data[CONF_PORT]
        )
    except CannotConnect as err:
        raise ConfigEntryNotReady(
            f"Cannot reach the charger at {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}: {err}"
        ) from err

    coordinator = IsdtCoordinator(hass, entry, info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    # The charger device first, so that the slot devices can refer to it.
    device_registry = dr.async_get(hass)
    charger = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        manufacturer="ISDT",
        model=info.model,
        model_id=info.build_number,
        name=entry.title,
        hw_version=(
            f"{info.hw_version} (built {info.build_date})"
            if info.build_date
            else info.hw_version
        ),
        sw_version=info.app_version,
        serial_number=info.serial,
    )

    # Each slot is a device of its own, under the charger.
    slot_device_ids = [
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, slot_identifier(coordinator, slot))},
            name=f"{entry.title} Slot {slot.number:02d}",
            manufacturer="ISDT",
            model=f"{info.model} slot",
            via_device_id=charger.id,
        ).id
        for slot in coordinator.slots
    ]

    # The slots are where the charger is.
    _inherit_area(hass, charger.id, slot_device_ids)

    @callback
    def _charger_updated(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        if event.data["action"] == "update" and "area_id" in event.data["changes"]:
            _inherit_area(
                hass, charger.id, slot_device_ids, event.data["changes"]["area_id"]
            )

    entry.async_on_unload(
        async_track_device_registry_updated_event(hass, charger.id, _charger_updated)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


@callback
def _inherit_area(
    hass: HomeAssistant,
    charger_id: str,
    slot_device_ids: list[str],
    previous_area: str | None = None,
) -> None:
    """Put the slots in the charger's area.

    Home Assistant doesn't do that by itself, which would leave 24 slots to put in an area one
    by one. A slot that has been put in another area on purpose stays there: only slots without
    an area, or still in the charger's previous area, follow the charger.
    """
    device_registry = dr.async_get(hass)
    charger = device_registry.async_get(charger_id)
    if charger is None or charger.area_id is None:
        return
    for device_id in slot_device_ids:
        device = device_registry.async_get(device_id)
        if (
            device is not None
            and device.area_id != charger.area_id
            and device.area_id in (None, previous_area)
        ):
            device_registry.async_update_device(device_id, area_id=charger.area_id)


async def async_unload_entry(hass: HomeAssistant, entry: IsdtConfigEntry) -> bool:
    """Unload a charger."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: IsdtConfigEntry) -> None:
    """The charger was removed: withdraw its repairs."""
    for issue in list(ir.async_get(hass).issues.values()):
        if issue.domain == DOMAIN and issue.issue_id.startswith(f"{entry.entry_id}_"):
            ir.async_delete_issue(hass, DOMAIN, issue.issue_id)


async def _async_update_listener(hass: HomeAssistant, entry: IsdtConfigEntry) -> None:
    """Options changed: reload, so that they take effect."""
    await hass.config_entries.async_reload(entry.entry_id)
