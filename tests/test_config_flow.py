"""Adding a charger."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import patch

import pytest

from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.isdt.api import CannotConnect
from custom_components.isdt.const import DOMAIN

from .conftest import INFO


def _discovery(host: str = "192.168.111.180") -> ZeroconfServiceInfo:
    """What a bridge's advertisement looks like to the config flow."""
    return ZeroconfServiceInfo(
        ip_address=ip_address(host),
        ip_addresses=[ip_address(host)],
        port=24000,
        hostname="paj-01.local.",
        type="_isdt._tcp.local.",
        name=f"ISDT N24 {INFO.serial}._isdt._tcp.local.",
        properties={"serial": INFO.serial, "model": "N24", "version": "2.1.0"},
    )


@pytest.mark.usefixtures("mock_charger")
async def test_user(hass: HomeAssistant) -> None:
    """The charger is found at the given address, and identified by its serial number."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"host": "bridge.example", "port": 24000}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "N24"
    assert result["result"].unique_id == INFO.serial
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(result["result"].entry_id)


@pytest.mark.usefixtures("mock_charger")
async def test_zeroconf(hass: HomeAssistant) -> None:
    """A bridge advertises a charger; confirming it probes and sets it up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery()
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "N24"
    assert result["result"].unique_id == INFO.serial
    assert result["result"].data == {"host": "192.168.111.180", "port": 24000}
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(result["result"].entry_id)


async def test_zeroconf_already_configured_updates_address(hass: HomeAssistant) -> None:
    """A rediscovered charger is not added again, and a bridge that moved is followed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="N24",
        data={"host": "192.168.111.180", "port": 24000},
        unique_id=INFO.serial,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=_discovery("192.168.111.181")
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.168.111.181"


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """No bridge at the given address."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    with patch(
        "custom_components.isdt.config_flow.get_info", side_effect=CannotConnect("refused")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "bridge.example", "port": 24000}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
