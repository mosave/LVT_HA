# from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, VOLUME_TITLE
from .lvt_entity import LvtEntity

LVT_NUMBER_ADD_ENTITIES: AddEntitiesCallback = None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the LVT Speaker "number" config entry."""
    await async_setup_platform(hass, config_entry, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the LVT Speaker "number" platform."""
    global LVT_NUMBER_ADD_ENTITIES
    LVT_NUMBER_ADD_ENTITIES = async_add_entities
    lvt_api = hass.data[DOMAIN]

    for _, speaker in lvt_api.speakers.items():
        if "volume" not in speaker.entities:
            speaker.entities["volume"] = LvtVolumeEntity(hass, speaker)

    lvt_api.platform_loaded("number")


class LvtVolumeEntity(NumberEntity, LvtEntity):
    """Representation of LVT Speaker Volume entity"""

    async_add_entities: AddEntitiesCallback = None

    def __init__(self, hass, lvt_speaker) -> None:
        """Initialize the LVT Number entity"""
        global LVT_NUMBER_ADD_ENTITIES
        super().__init__(hass, lvt_speaker, "volume")
        self._attr_should_poll: bool = False
        self._att_icon = "mdi:account-voice"
        self._attr_name = VOLUME_TITLE.format(self.speaker_id)
        self._attr_assumed_state = False
        self._attr_mode = NumberMode.SLIDER
        self._attr_min_value = 0
        self._attr_max_value = 100
        self._attr_step = 10
        self._attr_value = 30
        LVT_NUMBER_ADD_ENTITIES([self])

    def set_value(self, value: int) -> None:
        """Update the current value."""
        if self.enabled:
            is_updated = int(self._attr_value) != int(value)
            self._attr_value = value
            if is_updated:
                self.schedule_update_ha_state()
