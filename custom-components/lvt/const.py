"""Constants for the Lite Voice Terminal integration."""

from homeassistant.util import slugify

DOMAIN = "lvt"
LVT_PLATFORMS: list[str] = ["binary_sensor", "number", "select"]

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 7999

IMPORTANCE_TITLE = "Message Filter [{}]"
VOLUME_TITLE = "Volume [{}]"
ONLINESTATUS_TITLE = "Online status [{}]"
SERVER_ONLINESTATUS_TITLE = "LVT Server Online status"

DISCOVERY_TASK = "lvt_discovery_task"


def lvt_unique_id(speaker_id: str, e_id: str) -> str:
    eid = DOMAIN + "_"
    if speaker_id is not None:
        eid += slugify(speaker_id) + "_"
    eid += slugify(e_id)
    return eid


def lvt_entity_id(speaker_id: str, e_id: str) -> str:
    return DOMAIN + "." + lvt_unique_id(speaker_id, e_id)
