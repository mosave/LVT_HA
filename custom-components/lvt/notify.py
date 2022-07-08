"""LVT support for notify component."""
from typing import Any
import voluptuous as vol
from config.custom_components.lvt.lvt import LvtApi
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
CONF_PLAY = "play"
CONF_SAY = "say"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SPEAKER, default=""): cv.string,
        vol.Required(CONF_IMPORTANCE): cv.string,
        vol.Optional(CONF_PLAY, default=""): cv.string,
        vol.Optional(CONF_SAY, default=""): cv.string,
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
        say_template = config[CONF_SAY]
        if bool(config[CONF_PLAY]):
            self.play = template.Template(config[CONF_PLAY], hass)
        else:
            self.play = None
            if not bool(say_template):
                say_template = " {% if title is defined %}{{ title }}{% endif %} .;,- {{ message }}"

        if bool(say_template):
            self.say = template.Template(say_template, hass)
        else:
            self.say = None

    async def async_send_message(self, message="", **kwargs):
        """Send a message to LVT."""
        lvt_api: LvtApi = self.hass.data[DOMAIN]
        kwargs["message"] = message
        data = kwargs.get(ATTR_DATA)
        if data is None:
            data = {}

        speaker = kwargs.get("trigger")
        data["speaker"] = speaker if bool(speaker) else self.speaker
        data["importance"] = self.importance

        if self.play is not None:
            data["play"] = self.play.async_render(kwargs)
            call = ServiceCall(DOMAIN, "lvt.play", data=data)
            await lvt_api.handle_play(call)

        if self.say is not None:
            data["say"] = self.say.async_render(kwargs)
            call = ServiceCall(DOMAIN, "lvt.say", data=data)
            await lvt_api.handle_say(call)
