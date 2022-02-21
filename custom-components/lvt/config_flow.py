"""Config flow for Lite Voice Terminal integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from .lvt import (
    LvtApi,
    async_server_test,
)
from homeassistant.core import callback

# from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

# from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN, DEFAULT_SERVER, DEFAULT_PORT, SSL_MODES, ssl_mode_to_int


_LOGGER = logging.getLogger(__name__)


def data_schema(lvt_api: LvtApi = None, user_input=None) -> str:
    if lvt_api is not None:
        _server = lvt_api.server
        _port = lvt_api.port
        _password = lvt_api.password
        _ssl = SSL_MODES[lvt_api.ssl_mode]
    elif user_input is not None:
        _server = user_input["server"]
        _port = user_input["port"]
        _password = user_input["password"] if "password" in user_input else None
        _ssl = user_input["ssl"] if "ssl" in user_input else 0
    else:
        _server = DEFAULT_SERVER
        _port = DEFAULT_PORT
        _password = None
        _ssl = SSL_MODES[0]

    return vol.Schema(
        {
            vol.Required(
                "server",
                description={"suggested_value": _server},
            ): str,
            vol.Required(
                "port",
                description={"suggested_value": _port},
            ): int,
            vol.Optional(
                "password",
                description={"suggested_value": _password},
            ): str,
            vol.Required(
                "ssl",
                description={"suggested_value": _ssl},
                default=0,
            ): vol.In(SSL_MODES),
        }
    )


async def async_test(hass, user_input) -> bool:
    return await async_server_test(
        hass,
        user_input["server"],
        user_input["port"],
        user_input["password"] if "password" in user_input else None,
        ssl_mode_to_int(user_input["ssl"] if "ssl" in user_input else 0),
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lite Voice Terminal."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        await self.async_set_unique_id("LVT")
        self._abort_if_unique_id_configured(updates=user_input)

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=data_schema())

        if await async_test(self.hass, user_input):
            return self.async_create_entry(
                title="Lite Voice Terminal",
                data=user_input,
            )

        errors = {}
        errors["base"] = "Not able to connect LVT server"
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema(user_input=user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """HACS config flow options handler."""

    def __init__(self, config_entry):
        """Initialize HACS options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """async_step_init"""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        lvt_api: LvtApi = self.hass.data.get(DOMAIN)
        if lvt_api is None:
            return self.async_abort(reason="not_setup")

        errors = {}
        if user_input is not None:
            if await async_test(self.hass, user_input):
                return self.async_create_entry(
                    title=f"LVT Server [{user_input['server']}]",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"
            schema = data_schema(user_input=user_input)
        # elif lvtApi.config_type != CONFIG_TYPE_ENTRY:
        #     schema = vol.Schema({vol.Optional("not_in_use", default=""): str})
        else:
            schema = data_schema(lvt_api=lvt_api)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
