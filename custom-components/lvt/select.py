from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    IMPORTANCE_TITLE,
    LVT_PLATFORMS,
)
from .lvt_entity import LvtEntity

LVT_SELECT_ADD_ENTITIES: AddEntitiesCallback = None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, config_entry, async_add_entities)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the LVT Speaker "number" platform."""
    global LVT_SELECT_ADD_ENTITIES
    LVT_SELECT_ADD_ENTITIES = async_add_entities
    lvt_api = hass.data[DOMAIN]
    for _, speaker in lvt_api.speakers.items():
        speaker.entities["filter"] = LvtFilterEntity(hass, speaker)

    lvt_api.loaded_platforms.add("select")
    if set(lvt_api.loaded_platforms) == set(LVT_PLATFORMS):
        lvt_api.start()


class LvtFilterEntity(SelectEntity, LvtEntity):
    """LVT Speaker Importance Filter entity"""

    _attr_device_class = "importance__filter"

    def __init__(self, hass, lvt_speaker) -> None:
        """Initialize the LVT Speaker Importance Filter entity"""
        global LVT_SELECT_ADD_ENTITIES
        super().__init__(hass, lvt_speaker, "filter")

        self._attr_icon = "mdi:account-filter"
        self._attr_device_class = "importance__filter"
        self._attr_name = IMPORTANCE_TITLE.format(self.speaker_id)

        self._attr_options = [
            "0",
            "1",
            "2",
            "3",
            "4",
        ]
        self._attr_current_option = self._attr_options[0]
        LVT_SELECT_ADD_ENTITIES([self])

    def select_option(self, option: str) -> None:
        """Update the current selected option."""
        if self.enabled:
            flt = int(list(str(f"{option}:z").partition(":"))[0])
            flt = 0 if flt < 0 else (4 if flt > 4 else flt)
            flt = self._attr_options[flt]
            is_updated = self._attr_current_option != flt
            self._attr_current_option = flt
            if is_updated:
                self.schedule_update_ha_state()
