"""LVT automation trigger rules."""

from typing import Any
import voluptuous as vol
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType
from .const import *

_TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        # vol.Optional(CONF_EVENT, default=DEFAULT_EVENT): vol .Any(
        #     EVENT_INTENT, EVENT_ONLINE
        # ),
        vol.Required(CONF_INTENT): cv.string,
        vol.Optional(CONF_SPEAKER): cv.string,
        vol.Optional(CONF_DATA): object,
    },
    # extra=1,
)


async def async_validate_trigger_config(hass, config) -> ConfigType:
    """Validate trigger config."""
    config = _TRIGGER_SCHEMA(config)
    return config


async def async_attach_trigger(
    hass, config, action, automation_info, *, platform_type: str = DOMAIN
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    if DOMAIN in hass.data:
        lvt_api = hass.data[DOMAIN]
        lvt_api.add_trigger(config, action, automation_info)

    @callback
    def async_remove() -> None:
        """Remove state listeners async."""
        return

    return async_remove
