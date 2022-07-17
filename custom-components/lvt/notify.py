"""LVT support for notify component."""
from typing import Any
import voluptuous as vol
from .lvt import LvtApi
from homeassistant.core import ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import template
from .const import DOMAIN
from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)


CONF_SPEAKER = "speaker"
CONF_IMPORTANCE = "importance"
CONF_VOLUME = "volume"
CONF_PLAY = "play"
CONF_SAY = "say"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SPEAKER, default=""): cv.string,
        vol.Required(CONF_IMPORTANCE): cv.string,
        vol.Optional(CONF_VOLUME, default=""): cv.string,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the LVT notification service."""
    return LVTNotificationService(hass, config)


class LVTNotificationService(BaseNotificationService):
    """Implementation of a notification service for LVT."""

    def __init__(self, hass, config):
        """Initialize the service."""
        self.speaker = config[CONF_SPEAKER]
        self.importance = config[CONF_IMPORTANCE]
        if config[CONF_VOLUME] is not None:
            try:
                self.volume = int(config[CONF_VOLUME])
                if self.volume < 0:
                    self.volume = 0
                elif self.volume > 100:
                    self.volume = 100
            except ValueError:
                self.volume = None

    async def async_send_message(self, message="", **kwargs):
        """Send a message to LVT."""
        lvt_api: LvtApi = self.hass.data[DOMAIN]
        data = kwargs.get(ATTR_DATA)
        if data is None:
            data = {}

        speaker = kwargs.get("trigger")
        data["speaker"] = speaker if bool(speaker) else self.speaker
        data["importance"] = self.importance
        volume = kwargs.get("volume")
        data["volume"] = volume if volume is not None else self.volume
        data["say"] = message if bool(message) else "Текст сообщения не задан"
        call = ServiceCall(DOMAIN, "lvt.say", data=data)
        await lvt_api.handle_say(call)
