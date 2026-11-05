"""Adding a charger."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.isdt.api import CannotConnect
from custom_components.isdt.const import DOMAIN

from .conftest import INFO


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
