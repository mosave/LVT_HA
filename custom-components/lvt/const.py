"""Constants for the Lite Voice Terminal integration."""

from homeassistant.util import slugify

DOMAIN = "lvt"
LVT_PLATFORMS: list[str] = ["binary_sensor", "number", "select"]

DEFAULT_SERVER = "127.0.0.1"
DEFAULT_PORT = 2700

IMPORTANCE_TITLE = "Message Filter [{}]"
VOLUME_TITLE = "Volume [{}]"
ONLINESTATUS_TITLE = "Online status [{}]"
SERVER_ONLINESTATUS_TITLE = "LVT Server Online status"

SSL_MODES = [
    "0: Unsecured connection",
    "1: SSL, no certificate validation",
    "2: SSL with valid certificate only",
]


def lvt_unique_id(speaker_id: str, e_id: str) -> str:
    eid = DOMAIN + "_"
    if speaker_id is not None:
        eid += slugify(speaker_id) + "_"
    eid += slugify(e_id)
    return eid


def lvt_entity_id(speaker_id: str, e_id: str) -> str:
    return DOMAIN + "." + lvt_unique_id(speaker_id, e_id)


def ssl_mode_to_int(ssl_mode: str) -> int:
    try:
        if str(ssl_mode) in SSL_MODES:
            mode = SSL_MODES.index(str(ssl_mode))
        else:
            mode = int(ssl_mode)

        if not isinstance(mode, int) or mode < 0 or mode > 2:
            mode = 0
    except Exception:
        mode = 0
    return mode
