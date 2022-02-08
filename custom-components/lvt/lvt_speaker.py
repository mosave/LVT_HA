"""Lite Voice Terminal - Speaker class implementation"""

import logging

from homeassistant.helpers.device_registry import DeviceEntry, DeviceRegistry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntry
from homeassistant.util import slugify
from .const import DOMAIN, lvt_unique_id
from .binary_sensor import LvtOnlineEntity
from .select import LvtFilterEntity
from .number import LvtVolumeEntity


_LOGGER = logging.getLogger(__name__)


class LvtSpeaker:
    """LVT Speaker class."""

    def __init__(self, hass, speaker_id, server_online: bool) -> None:
        self.hass = hass
        self.__id = speaker_id
        self.__info = {}
        self.__entities = {}
        self.__server_online = server_online
        # _LOGGER.info("LVT Speaker %s (%s) created", self._name, self._id)

    async def async_update(self, info: dict[str, any]):
        """ "Update LvtSpeaker state with dictionary sent by server"""
        _name = self.device_info["name"]
        _model = self.device_info["model"]
        _sw_version = self.device_info["sw_version"]
        self.__info = info

        device = self.device
        if device is not None:
            if not device.disabled:
                if (
                    _name != self.device_info["name"]
                    or _model != self.device_info["model"]
                    or _sw_version != self.device_info["sw_version"]
                ):
                    registry: DeviceRegistry = self.hass.data["device_registry"]
                    if registry is not None:
                        registry.async_update_device(
                            self.device.id,
                            name=self.device_info["name"],
                            model=self.device_info["model"],
                            sw_version=self.device_info["sw_version"],
                        )

                self.update_entities()
        elif self.online:
            self.create_entities()
            self.update_entities()

    def set_server_online(self, is_online: bool):
        """ "Update speaker' HA entities reflecting LVT API connection status"""
        self.__server_online = is_online
        self.update_entities()

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return (
            str(self.__info["Name"])
            if "Name" in self.__info
            else f"LVT Speaker [{self.id}]"
        )

    @property
    def id(self) -> str:
        """Get the LVT Speaker Id"""
        return self.__id

    @property
    def entities(self) -> dict[str, any]:
        """Get the LVT Speaker Id"""
        return self.__entities

    @property
    def online(self) -> bool:
        """Is speaker online now?"""
        if not self.__server_online or "Connected" not in self.__info:
            return False
        return bool(self.__info["Connected"])

    @property
    def volume(self) -> int:
        """Speaker volume"""
        if "volume" in self.entities:
            return int(self.entities["volume"].value)
        return 30

    @property
    def out_of_sync(self) -> bool:
        """Check if volume should be updated to LVT server"""
        result = False
        if "volume" in self.entities:
            vol = int(self.__info["Volume"]) if "Volume" in self.__info else None
            result = result or bool(self.volume != vol)
        if "filter" in self.entities:
            flt = int(self.__info["Filter"]) if "Filter" in self.__info else 0
            result = result or (self.filter != flt)
        return result

    @property
    def filter(self) -> int:
        if "filter" not in self.entities:
            return 0
        level = self.entities["filter"].current_option
        if level is None:
            return 0
        level = int(list(str(level + ":").partition(":"))[0])
        return 0 if level < 0 else (4 if level > 4 else level)

    @property
    def suggested_area(self) -> str:
        """Terminal software version"""
        return str(self.__info["Location"]) if "Location" in self.__info else None

    @property
    def version(self) -> str:
        """Terminal software version"""
        return str(self.__info["Version"]) if "Version" in self.__info else None

    @property
    def address(self) -> str:
        """Terminal IP address"""
        return str(self.__info["Address"]) if "Address" in self.__info else None

    @property
    def device_info(self) -> DeviceInfo:
        """Unified device info dictionary for LvtSpeaker."""
        return {
            "identifiers": {(DOMAIN, slugify(self.id))},
            "name": self.name,
            "manufacturer": "Lite Voice Terminal",
            "model": "Speaker at {}".format(self.address),
            "suggested_area": self.suggested_area,
            "sw_version": self.version,
        }

    @property
    def device(self) -> DeviceEntry:
        """ "Retrieve Speaker device from device registry"""
        registry: DeviceRegistry = self.hass.data["device_registry"]
        if registry is not None:
            return registry.async_get_device({(DOMAIN, slugify(self.id))})
        else:
            return None

    def get_entity_entry(self, eid: str) -> RegistryEntry:
        """Get entity description from registry"""
        registry: EntityRegistry = self.hass.data["entity_registry"]
        if registry is not None:
            uid = lvt_unique_id(self.id, eid)
            for _, entry in registry.entities.items():
                if entry.platform == DOMAIN and entry.unique_id == uid:
                    return entry
        return None

    def create_entities(self):
        """Create LvtSpeaker HA entities"""
        if self.get_entity_entry("online") is None:
            self.entities["online"] = LvtOnlineEntity(self.hass, self)

        if self.get_entity_entry("filter") is None:
            self.entities["filter"] = LvtFilterEntity(self.hass, self)

        if self.get_entity_entry("volume") is None:
            self.entities["volume"] = LvtVolumeEntity(self.hass, self)

    def update_entities(self):
        """Synchronize HA entities state with LvtSpeaker state"""
        if "online" in self.entities:
            self.entities["online"].set_online(self.online)

        if "volume" in self.entities:
            self.entities["volume"].set_online(self.online)
            if "Volume" in self.__info:
                self.entities["volume"].set_value(int(self.__info["Volume"]))

        if "filter" in self.entities:
            self.entities["filter"].set_online(self.online)
            if "Filter" in self.__info:
                self.entities["filter"].select_option(int(self.__info["Filter"]))

        return
