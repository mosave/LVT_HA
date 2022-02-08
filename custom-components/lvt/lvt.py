"""Pandora Car Alarm System API."""

# import asyncio
import asyncio
import json
import logging
import random
import time

import aiohttp

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .lvt_speaker import LvtSpeaker
from .const import DOMAIN, CONFIG_TYPE_YAML

# region Constants
# API Server Authorization
MSG_API_AUTHORIZE = "Authorize"

# Query for LVT server status or server status update
MSG_API_SERVER_STATUS = "ServerStatus"

# Terminals status update:
MSG_API_SPEAKER_STATUS = "Status"

# Установить громкость
MSG_API_VOLUME = "Volume"

# Проговорить текст
MSG_API_SAY = "Say"

# endregion

_LOGGER = logging.getLogger(__name__)


class LvtApi:
    """LVT API class."""

    config_type = CONFIG_TYPE_YAML
    # region __init__ / __del__
    def __init__(
        self,
        hass: HomeAssistantType,
        server: str,
        port: int,
        password: str,
    ) -> None:
        """Constructor"""
        self._api_id = str(random.randrange(100, 999))
        self.hass: HomeAssistantType = hass
        self.session = async_get_clientsession(hass, verify_ssl=False)
        self.__entities = {}
        self.__speakers = {}
        self.async_add_entities: AddEntitiesCallback = None
        self.__online = False
        self.__client_task = None
        self.__ws = None
        self.__queue = []
        self.__speakers_synced = time.time()
        self.__wstask_id = str(random.randrange(100, 999))
        self.create_registered_speakers()
        hass.services.async_register(DOMAIN, "say", self.handle_say)

        self.configure(server, port, password)

    def __del__(self):
        """Destructor (just in case)"""
        self.stop()
        self.hass.services.async_remove(DOMAIN, "say")

    def configure(
        self,
        server: str,
        port: int,
        password: str,
    ) -> None:
        """Set LvtApi options"""
        self.stop()
        self.__online = False
        self.__authorized = False
        self.__server = server if server is not None else "127.0.0.1"
        self.__port = port if port is not None else 7999
        self.__password = password
        self.loaded_platforms = set()

    # endregion

    # region properties
    @property
    def server(self) -> str:
        """LVT Server address or host"""
        return self.__server

    @property
    def port(self) -> int:
        """LVT Server port number"""
        return self.__port

    @property
    def password(self) -> str:
        """LVT Server connection password"""
        return self.__password

    @property
    def entities(self) -> dict[str, any]:
        """Get the LVT Speaker Id"""
        return self.__entities

    @property
    def speakers(self) -> dict:
        """Accessor"""
        return self.__speakers

    @property
    def online(self) -> bool:
        return self.__online

    @online.setter
    def online(self, is_online: bool):
        """Update .online property and "lvt.online" entity"""
        if is_online != self.__online:
            self.logDebug(
                "Connected to LVT server"
                if is_online
                else "Disconnected from LVT server"
            )
            self.__online = is_online
            if not is_online:
                self.__authorized = False

            if "online" in self.entities:
                self.entities["online"].set_online(is_online)

            for _, speaker in self.speakers.items():
                speaker.set_server_online(is_online)

    @property
    def authorized(self) -> bool:
        return self.__authorized

    # endregion

    # region WebSock client implementation: start / stop / send_message / __websock_client
    def start(self):
        """Start LVT API Client task"""
        if self.__client_task is None:
            self.__wstask_id = str(random.randrange(100, 999))
            self.logDebug("Starting websock client")

            self.__online = False
            self.__client_task = self.hass.async_create_task(self.__websock_client())

    def stop(self):
        """Stop LVT API Client task"""
        if self.__client_task is not None:
            self.logDebug("Stopping websock client")
            self.__client_task.cancel()
            self.__client_task = None

    def send_message(
        self,
        msg: str,
        status_code: int = 0,
        status: str = None,
        data=None,
    ):
        message = {"Message": msg, "StatusCode": status_code}
        if status != None:
            message["Status"] = str(status)
        if data != None:
            message["Data"] = json.dumps(data)

        self.__queue.append(message)

    # def send_speaker_status(self, speaker_id: str, volume: int):
    #     if speaker_id in self.speakers:
    #         volume = int(volume)
    #         volume = 0 if volume < 0 else (100 if volume > 100 else volume)
    #         self.send_message(MSG_API_VOLUME, data={str(speaker_id): volume})

    def synchronize_speakers(self):
        self.__speakers_synced = time.time()
        data = {}
        for _, speaker in self.speakers.items():
            if speaker.out_of_sync:
                data[speaker.id] = {"Volume": speaker.volume, "Filter": speaker.filter}
        if data:
            self.send_message(MSG_API_SPEAKER_STATUS, data=data)

    async def __websock_client(self):
        while True:
            self.online = False
            try:
                url = f"http://{self.server}:{self.port}"
                self.logDebug("Connecting %s", url)
                self.__speakers_synced = time.time()
                async with self.session.ws_connect(url) as ws:
                    self.__ws = ws
                    session_started = time.time()
                    self.online = True
                    if self.password != None:
                        self.send_message(MSG_API_AUTHORIZE, data=str(self.password))
                    while True:
                        # Check if not authorized within 5 seconds
                        if not self.authorized and (
                            (time.time() - session_started) > 5
                        ):
                            self.logError("Not authorized!")
                            await ws.close()
                            break
                        while len(self.__queue) > 0:
                            await self.__ws.send_json(self.__queue[0])
                            self.__queue.pop(0)

                        if (time.time() - self.__speakers_synced) > 10:
                            self.synchronize_speakers()

                        msg = None  # команда
                        status_code = 0  # 0 if Ok
                        # status = None  # сообщение об ошибке (опционально)
                        data = None  # Данные, зависит от msg
                        try:
                            msg = await ws.receive(0.5)
                            if msg is None:
                                pass
                            elif msg.type == aiohttp.WSMsgType.TEXT:
                                # Разбираем пакет, тупо игнорируя ошибки
                                try:
                                    request = json.loads(str(msg.data))
                                    msg = str(request["Message"])
                                    status_code = (
                                        int(request["StatusCode"])
                                        if "StatusCode" in request
                                        else 0
                                    )
                                    status = (
                                        str(request["Status"])
                                        if "Status" in request
                                        else None
                                    )
                                    data = (
                                        json.loads(str(request["Data"]))
                                        if "Data" in request
                                        else None
                                    )
                                except Exception:
                                    msg = None
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                msg = None
                                break
                            else:
                                msg = None
                        except asyncio.TimeoutError:
                            msg = None
                        # Process message received
                        if msg == MSG_API_AUTHORIZE:  # LVT Server status message
                            if status_code == 0:
                                self.logDebug("Authorized")
                                self.__authorized = True
                            else:
                                self.logError(
                                    "Authnentication failure: Invalid password."
                                )
                                await ws.close()
                        if msg == MSG_API_SERVER_STATUS:  # LVT Server status message
                            await self._async_update_server_status(data)
                            if "Terminals" in data:
                                for _, speaker in data["Terminals"].items():
                                    await self._async_update_speaker_status(speaker)
                            to_delete = [
                                speaker_id
                                for speaker_id in self.speakers
                                if speaker_id not in data["Terminals"]
                            ]
                            for speaker_id in to_delete:
                                await self._async_delete_speaker(speaker_id)

                        elif msg == MSG_API_SPEAKER_STATUS:  # Speaker status update
                            for _, speaker in data.items():
                                await self._async_update_speaker_status(speaker)

            except aiohttp.ClientConnectionError as e:
                self.logWarning("Error connecting server: %s", str(e))
                await asyncio.sleep(5)
            except Exception as e:
                self.logError("API error [%s]: %s", type(e).__name__, str(e))
                await asyncio.sleep(5)
            except:
                self.logDebug("API client stopped")
                break
            finally:
                self.online = False

    # endregion

    # region speaker manipulation: update, delete, create etc
    async def _async_update_server_status(self, info: dict[str, any]):
        """Update server entities with LVT server data"""
        try:
            pass
        except Exception as e:
            self.logError(
                "Error [%s] updating LVT Server status %s ", type(e).__name__, str(e)
            )

    async def _async_update_speaker_status(self, info: dict[str, any]):
        """Update speaker entities with LVT data
        * Speaker is already registered in HA: update all entities
        * Speaker is online but is not yet registered with HA : create new set of entities
        """
        if not info or not "Id" in info:
            return

        try:
            speaker_id = info["Id"]
            # if speaker_id != "speaker2":
            #     return

            if speaker_id in self.speakers:
                speaker = self.speakers[speaker_id]
            else:
                speaker = self.speakers[speaker_id] = LvtSpeaker(
                    self.hass, speaker_id, self.online
                )

            await speaker.async_update(info)
        except Exception as e:
            self.logError(
                'Error [%s] "%s" updating speaker: %s ',
                type(e).__name__,
                str(e),
                str(info),
            )

    async def _async_delete_speaker(self, speaker_id: str):
        registry = self.hass.data["device_registry"]
        if registry is not None:
            if speaker_id in self.speakers:
                speaker = self.speakers[speaker_id]
                if speaker.device is not None:
                    await registry.async_remove_device(speaker.device.id)
                    del self.speakers[speaker_id]

    def create_registered_speakers(self) -> list:
        ids = []
        registry = self.hass.data["device_registry"]
        if registry is not None:
            for _, device in registry.devices.items():
                domain, speaker_id = list(device.identifiers)[0]
                if domain == DOMAIN:
                    self.speakers[speaker_id] = LvtSpeaker(
                        self.hass, speaker_id, self.online
                    )

        return ids

    # endregion

    # region handle_say
    async def handle_say(self, call):
        """Handle "say" service call."""
        if not self.online:
            return
        text = call.data.get("text", "")
        if not text:
            return
        self.synchronize_speakers()
        importance = int(list(call.data.get("importance", "0:").partition(":"))[0])

        # Collect IDs all "enabled" speakers:
        device_id = call.data.get("speaker", None)
        ids = []
        for _, speaker in self.speakers.items():
            if speaker.online and importance >= speaker.filter and speaker.volume > 0:
                if device_id is None:
                    ids.append(speaker.id)
                if speaker.device is not None and (speaker.device.id == device_id):
                    ids.append(speaker.id)
        if len(ids) > 0:
            data = {"Text": text, "Importance": importance, "Terminals": ids}
            self.send_message(MSG_API_SAY, data=data)

    # endregion

    # region logInfo / logDebug / logWarning / logError
    def logInfo(self, msg: str, *args, **kwargs):
        s = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.info(s, *args, **kwargs)

    def logDebug(self, msg: str, *args, **kwargs):
        s = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.debug(s, *args, **kwargs)

    def logWarning(self, msg: str, *args, **kwargs):
        s = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.warning(s, *args, **kwargs)

    def logError(self, msg: str, *args, **kwargs):
        s = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.error(s, *args, **kwargs)

    # endregion


async def async_server_test(
    hass: HomeAssistantType, server: str, port: int, password: str
) -> bool:
    """Test if we can LVT API Server is available"""
    _ok = False

    try:
        session = async_get_clientsession(hass, verify_ssl=False)
        async with session.ws_connect(f"http://{server}:{port}") as ws:
            if password is not None:
                request = {}
                request["Message"] = MSG_API_AUTHORIZE
                request["Data"] = json.dumps(password)
                await ws.send_json(request)

            msg = await ws.receive(5)
            request = json.loads(str(msg.data))
            msg = str(request["Message"])
            status_code = int(request["StatusCode"]) if "StatusCode" in request else 0
            if msg == MSG_API_AUTHORIZE and (status_code == 0):
                _ok = True
            await ws.close()
    except:
        _ok = False

    return _ok
