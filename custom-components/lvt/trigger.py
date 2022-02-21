"""LVT automation trigger rules."""
import logging

import voluptuous as vol

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType
from .const import *

# mypy: allow-incomplete-defs, allow-untyped-defs
# mypy: no-check-untyped-defs

EVENT_INTENT = "intent"
EVENT_ONLINE = "online"
DEFAULT_EVENT = EVENT_INTENT

_LOGGER = logging.getLogger(__name__)

_EVENT_DESCRIPTION = {
    EVENT_INTENT: "intent fired",
    EVENT_ONLINE: "online status changed",
}

_TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): DOMAIN,
        # vol.Optional(CONF_EVENT, default=DEFAULT_EVENT): vol .Any(
        #     EVENT_INTENT, EVENT_ONLINE
        # ),
        vol.Required(CONF_INTENT): cv.string,
        vol.Optional(CONF_SPEAKER): cv.string,
        vol.Optional(CONF_DATA, default={}): any,
    }
)


async def async_validate_trigger_config(
    hass: HomeAssistant, config: ConfigType
) -> ConfigType:
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
