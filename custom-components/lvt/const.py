"""Constants for the Lite Voice Terminal integration."""

from typing import Final
from homeassistant.util import slugify

DOMAIN: Final = "lvt"
LVT_PLATFORMS: list[str] = ["binary_sensor", "number", "select"]

DEFAULT_SERVER: Final = "127.0.0.1"
DEFAULT_PORT: Final = 2700

CONF_PLATFORM: Final = "platform"
CONF_INTENT: Final = "intent"
CONF_SPEAKER: Final = "speaker"
CONF_DATA: Final = "data"

IMPORTANCE_TITLE = "Message Filter [{}]"
VOLUME_TITLE = "Volume [{}]"
ONLINESTATUS_TITLE = "Online status [{}]"
SERVER_ONLINESTATUS_TITLE = "LVT Server Online status"


SSL_MODES = [
    "0: Unsecured connection",
    "1: SSL, no certificate validation",
    "2: SSL with valid certificate only",
]

# region API messages
# API Server Authorization
MSG_API_AUTHORIZE: Final = "Authorize"

# LVT server reporting for error
MSG_API_ERROR: Final = "Error"

# Query for LVT server status or server status update
MSG_API_SERVER_STATUS: Final = "ServerStatus"

# Initialize LVT server with list of intents to track.
MSG_API_SET_INTENTS: Final = "SetIntents"

# Request from LVT server to fire an intent
MSG_API_FIRE_INTENT: Final = "FireIntent"

# Terminals status update:
MSG_API_SPEAKER_STATUS: Final = "Status"

# Установить громкость
MSG_API_VOLUME: Final = "Volume"

# Проиграть звуковой эффект
MSG_API_PLAY: Final = "Play"

# Проговорить текст
MSG_API_SAY: Final = "Say"

# Запустить диалог подтверждения
# MSG_API_CONFIRM = "Confirm"

# Запустить диалог выбора варианта из списка возможных
MSG_API_NEGOTIATE: Final = "Negotiate"
# endregion


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
