from homeassistant.helpers.entity import Entity

from .const import (
    lvt_entity_id,
    lvt_unique_id,
)


class LvtEntity(Entity):
    """LVT Entity base class."""

    def __init__(self, hass, lvt_speaker, e_id: str):
        """Initialize LVT Speaker Online sensor"""
        self._attr_should_poll = False
        self._disabled_reported = True
        self._attr_state = None
        self.hass = hass
        self._attr_speaker = lvt_speaker
        self._attr_available = False

        self.entity_id = lvt_entity_id(self.speaker_id, e_id)
        self._attr_unique_id = lvt_unique_id(self.speaker_id, e_id)

    @property
    def speaker_id(self) -> str:
        return self.speaker.id if self.speaker is not None else None

    @property
    def speaker(self):
        return self._attr_speaker

    @property
    def device_info(self):
        if self.speaker is not None:
            return self.speaker.device_info
        return None

    def set_online(self, is_online: bool):
        if self.enabled:
            updated = bool(self._attr_available != is_online)
            self._attr_available = is_online
            if updated:
                self.schedule_update_ha_state()
