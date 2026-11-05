"""The ISDT charger integration.

Talks to an ISDT charger through an isdttool bridge (`isdttool serve`) on the network. The
charger itself can be plugged into any machine that runs the bridge.
"""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .api import CannotConnect, get_info
from .const import DOMAIN
from .coordinator import IsdtConfigEntry, IsdtCoordinator
from .entity import slot_identifier

PLATFORMS = [Platform.EVENT, Platform.SENSOR]


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
    for slot in coordinator.slots:
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, slot_identifier(coordinator, slot))},
            name=f"{entry.title} Slot {slot.number:02d}",
            manufacturer="ISDT",
            model=f"{info.model} slot",
            via_device_id=charger.id,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


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
