from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ONLINESTATUS_TITLE,
    SERVER_ONLINESTATUS_TITLE,
)
from .lvt_entity import LvtEntity

LVT_BINARY_SENSOR_ADD_ENTITIES: AddEntitiesCallback = None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the LVT Speaker "binary_sensor" config entry."""
    await async_setup_platform(hass, config_entry, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the LVT Speaker binary_sensor platform."""
    global LVT_BINARY_SENSOR_ADD_ENTITIES
    LVT_BINARY_SENSOR_ADD_ENTITIES = async_add_entities
    lvt_api = hass.data[DOMAIN]

    if "online" not in lvt_api.entities:
        lvt_api.entities["online"] = LvtOnlineEntity(hass, None)

    for _, speaker in lvt_api.speakers.items():
        if "online" not in speaker.entities:
            speaker.entities["online"] = LvtOnlineEntity(hass, speaker)

    lvt_api.platform_loaded("binary_sensor")


class LvtOnlineEntity(BinarySensorEntity, LvtEntity):
    """LVT Speaker Online binary sensor."""

    _attr_should_poll = False

    def __init__(self, hass, lvt_speaker):
        """Initialize LVT Speaker Online sensor"""
        global LVT_BINARY_SENSOR_ADD_ENTITIES
        super().__init__(hass, lvt_speaker, "online")

        self._state = None
        self._attr_icon = {True: "mdi:broadcast", False: "mdi:broadcast-off"}
        self._attr_device_class = DEVICE_CLASS_CONNECTIVITY
        if self.speaker_id is None:
            self._attr_name = SERVER_ONLINESTATUS_TITLE
        else:
            self._attr_name = ONLINESTATUS_TITLE.format(self.speaker_id)

        self._attr_is_on: bool = False
        self._attr_should_poll: bool = False
        LVT_BINARY_SENSOR_ADD_ENTITIES([self])

    def set_online(self, is_online: bool):
        """Set online status"""
        if self.enabled:
            updated = bool(self._attr_is_on) != bool(is_online) or bool(
                self._attr_available != is_online
            )
            if updated:
                self._attr_is_on = bool(is_online)
                self._attr_available = bool(is_online)
                self.schedule_update_ha_state()

    @property
    def icon(self) -> str:
        """Icon for the online status."""
        if not hasattr(self, "_attr_icon"):
            icon = None
        elif isinstance(self._attr_icon, dict):
            icon = self._attr_icon[bool(self.is_on)]
        else:
            icon = self._attr_icon
        return icon
