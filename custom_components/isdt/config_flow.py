"""Config flow for the ISDT charger integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import CannotConnect, ChargerInfo, get_info
from .const import (
    CONF_WORN_RESISTANCE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WORN_RESISTANCE,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import IsdtConfigEntry

_LOGGER = logging.getLogger(__name__)


def _connection_schema(host: str = "", port: int = DEFAULT_PORT) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): cv.string,
            vol.Required(CONF_PORT, default=port): cv.port,
        }
    )


def _unique_id(info: ChargerInfo, host: str, port: int) -> str:
    """The charger's serial number. The bridge answers with the USB serial number for chargers
    that don't report one themselves. Without either, the address is all there is."""
    return info.serial or f"{host}:{port}"


class IsdtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an ISDT charger."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] = {}
        self._discovered_name: str | None = None

    async def _async_probe(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> ChargerInfo | None:
        try:
            return await self.hass.async_add_executor_job(
                get_info, user_input[CONF_HOST], user_input[CONF_PORT]
            )
        except CannotConnect as err:
            _LOGGER.debug("Cannot connect to %s: %s", user_input, err)
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error talking to the charger")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the bridge's address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info = await self._async_probe(user_input, errors)
            if info is not None:
                await self.async_set_unique_id(
                    _unique_id(info, user_input[CONF_HOST], user_input[CONF_PORT])
                )
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(title=f"{info.model}", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                _connection_schema(), user_input or {}
            ),
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """A bridge advertised a charger on the network (see the isdttool docs, zeroconf.md)."""
        host = str(discovery_info.ip_address)
        port = discovery_info.port or DEFAULT_PORT
        serial = discovery_info.properties.get("serial")
        model = discovery_info.properties.get("model")

        # The bridge advertises the same serial a client reads over the link, so a charger that
        # is already set up — by hand or by an earlier discovery — is recognised here, and its
        # address is updated if the bridge moved.
        if serial:
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: port}
            )

        self._discovered = {CONF_HOST: host, CONF_PORT: port}
        self._discovered_name = model or "ISDT charger"
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered charger, then probe it to identify it for real."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info = await self._async_probe(self._discovered, errors)
            if info is not None:
                await self.async_set_unique_id(
                    _unique_id(info, self._discovered[CONF_HOST], self._discovered[CONF_PORT])
                )
                self._abort_if_unique_id_configured(updates=self._discovered)
                return self.async_create_entry(title=f"{info.model}", data=self._discovered)

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"name": self._discovered_name or "ISDT charger"},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the bridge's address, for example after moving the charger."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            info = await self._async_probe(user_input, errors)
            if info is not None:
                await self.async_set_unique_id(
                    _unique_id(info, user_input[CONF_HOST], user_input[CONF_PORT])
                )
                if info.serial:
                    self._abort_if_unique_id_mismatch(reason="wrong_charger")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_connection_schema(entry.data[CONF_HOST], entry.data[CONF_PORT]),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: IsdtConfigEntry) -> OptionsFlow:
        """Options."""
        return IsdtOptionsFlow()


class IsdtOptionsFlow(OptionsFlow):
    """Poll interval, and the resistance above which a cell counts as worn."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                    vol.Required(
                        CONF_WORN_RESISTANCE,
                        default=options.get(CONF_WORN_RESISTANCE, DEFAULT_WORN_RESISTANCE),
                    ): vol.All(vol.Coerce(int), vol.Range(min=50, max=5000)),
                }
            ),
        )
