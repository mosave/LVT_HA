"""Pandora Car Alarm System API."""

# import asyncio
import asyncio
import json
import logging
import random
import ssl
import time
from typing import OrderedDict

import aiohttp
from homeassistant.core import HassJob

from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import intent
from .const import *
from .lvt_speaker import LvtSpeaker

_LOGGER = logging.getLogger(__name__)

# region get_protocol / get_ssl_context #########################################
def get_protocol(ssl_mode: int) -> str:
    return "https" if ssl_mode > 0 else "http"


def get_ssl_context(ssl_mode: int):
    if ssl_mode == 2:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    elif ssl_mode == 1:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    else:
        context = None
    return context


# endregion


class LvtApi:
    """LVT API class."""

    # region __init__ / __del__ #################################################
    def __init__(
        self,
        hass: HomeAssistantType,
    ) -> None:
        """Constructor"""
        self._api_id = str(random.randrange(100, 999))
        self.hass: HomeAssistantType = hass
        self.session = async_get_clientsession(hass)
        self.__entities = {}
        self.__speakers = {}
        self.__server = None
        self.__port = None
        self.__password = None
        self.__ssl_mode = 0
        self.__online = False
        self.__triggers = []
        self.__client_task = None
        self.__ws = None
        self.__queue = []
        self.__speakers_synced = time.time()
        self.__wstask_id = str(random.randrange(100, 999))
        self.__intents = []
        hass.services.async_register(DOMAIN, "play", self.handle_play)
        hass.services.async_register(DOMAIN, "say", self.handle_say)
        hass.services.async_register(DOMAIN, "confirm", self.handle_confirm)
        hass.services.async_register(DOMAIN, "negotiate", self.handle_negotiate)
        self.__loaded_platforms = set()

        self.start()

    def __del__(self):
        """Destructor (just in case)"""
        self.stop()
        self.hass.services.async_remove(DOMAIN, "play")
        self.hass.services.async_remove(DOMAIN, "say")
        self.hass.services.async_remove(DOMAIN, "confirm")
        self.hass.services.async_remove(DOMAIN, "negotiate")

    def configure_connection(
        self, server: str, port: int, password: str, _ssl_mode: int
    ) -> None:
        """Set LvtApi options"""
        self.stop()
        self.__online = False
        self.__authorized = False
        self.__server = server if server is not None else "127.0.0.1"
        self.__port = port if port is not None else 2700
        self.__password = password if password is not None else ""
        self.__ssl_mode = (
            int(_ssl_mode)
            if _ssl_mode is not None
            and isinstance(_ssl_mode, int)
            and _ssl_mode >= 0
            and _ssl_mode <= 2
            else 0
        )
        self.__loaded_platforms = set()
        self.create_registered_speakers()
        self.start()

    def configure_intents(self):
        # process and check intents passed
        if self.online:
            pass

    def platform_loaded(self, platform):
        self.__loaded_platforms.add(platform)

    def add_trigger(self, config, action, automation):
        self.__triggers.append(
            {"config": config, "action": action, "automation": automation}
        )

    # endregion

    # region properties #########################################################
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
    def ssl_mode(self) -> int:
        """LVT Server SSL status"""
        return int(self.__ssl_mode)

    @property
    def entities(self) -> dict[str, any]:
        """Get the LVT Speaker Id"""
        return self.__entities

    @property
    def speakers(self) -> dict:
        """Accessor"""
        return self.__speakers

    @property
    def intents(self) -> dict:
        return self.__intents

    @property
    def online(self) -> bool:
        return self.__online

    @property
    def platforms_loaded(self) -> bool:
        return set(self.__loaded_platforms) != set(LVT_PLATFORMS)

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

    def synchronize_speakers(self):
        self.__speakers_synced = time.time()
        data = {}
        for _, speaker in self.speakers.items():
            if speaker.out_of_sync:
                data[speaker.id] = {"Volume": speaker.volume, "Filter": speaker.filter}
        if data:
            self.send_message(MSG_API_SPEAKER_STATUS, data=data)

    def send_intents(self):
        self.send_message(MSG_API_SET_INTENTS, data=self.intents)

    async def __websock_client(self):
        self.logDebug(
            "Waiting for configuration and loading platforms: %s", LVT_PLATFORMS
        )
        session_started = time.time()
        error_reported = False
        while (
            self.platforms_loaded
            or not bool(self.__server)
            or not bool(self.__port)
            or not bool(self.__password)
        ):
            if ((time.time() - session_started) > 30) and not error_reported:
                error_reported = True
                if self.platforms_loaded:
                    self.logError("Not all LVT platforms loaded!")
                else:
                    self.logError(
                        "Missing Lite Voice Terminal connection config. Please consult LVT documentation"
                    )
            await asyncio.sleep(0.5)
        while True:
            self.online = False
            try:
                url = f"{get_protocol(self.ssl_mode)}://{self.server}:{self.port}/api"
                self.logDebug("Connecting %s", url)
                self.__speakers_synced = time.time()
                async with self.session.ws_connect(
                    url, heartbeat=10, ssl=get_ssl_context(self.ssl_mode)
                ) as ws:
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
                        status = None  # сообщение об ошибке (опционально)
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
                                self.send_intents()
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

                        elif msg == MSG_API_FIRE_INTENT:
                            if "Intent" not in data:
                                self.logError(
                                    "LVT API.FireIntent: Intent not specified "
                                )
                            # region Fire An Intent
                            intent_type = data["Intent"]
                            slots = data["Data"] if "Data" in data else {}
                            slots = {
                                key: {"value": value} for key, value in slots.items()
                            }
                            try:
                                response = await intent.async_handle(
                                    self.hass, DOMAIN, intent_type, slots
                                )
                                self.logInfo(str(response))

                            except intent.UnknownIntent as err:
                                self.logWarning(
                                    "Received unknown intent %s", intent_type
                                )

                            except intent.InvalidSlotInfo as err:
                                self.logError(
                                    "Received invalid slot data for intent %s: %s",
                                    intent_type,
                                    err,
                                )

                            except intent.IntentError as e:
                                self.logError(
                                    "Handling request for %s: %s %s",
                                    intent_type,
                                    type(e).__name__,
                                    e,
                                )
                            # endregion

                            # region Trigger Event
                            for trigger in self.__triggers:
                                if (
                                    str(trigger["config"]["intent"]).lower()
                                    == str(intent_type).lower()
                                ):
                                    job = HassJob(trigger["action"])
                                    trigger_data = trigger["automation"]["trigger_data"]
                                    speaker = (
                                        data["Data"]["Speaker"]
                                        if "Data" in data and "Speaker" in data["Data"]
                                        else None
                                    )

                                    self.hass.async_run_hass_job(
                                        job,
                                        {
                                            "trigger": {
                                                **trigger_data,
                                                "platform": DOMAIN,
                                                "intent": intent_type,
                                                "speaker": speaker,
                                                "description": f'Intent "{intent_type}" from "{speaker}"',
                                            }
                                        },
                                        None,
                                    )
                            # endregion
                        elif msg == MSG_API_ERROR:
                            self.logError(
                                "LVT Server error #%s: %s",
                                str(status_code),
                                str(status),
                            )

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

    # region speaker manipulation: update, delete, create etc ###################
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
                if domain == DOMAIN and (speaker_id not in self.speakers):
                    self.speakers[speaker_id] = LvtSpeaker(
                        self.hass, speaker_id, self.online
                    )

        return ids

    # endregion

    # region parse_speakers #####################################################
    def parse_speakers(self, speakers, active_only=True):
        """Resolve (list of) speaker IDs. Accepted values are:
        - speaker id
        - HA device id
        - ID/UID
        """

        all_speakers = []
        for _, speaker in self.speakers.items():
            if not active_only or speaker.online and speaker.volume > 0:
                all_speakers.append(speaker)

        if not bool(speakers):
            return all_speakers

        if isinstance(speakers, dict):
            speaker_ids = list(speakers.keys())
        else:
            speaker_ids = list(speakers)

        parsed_speakers = []

        for speaker_id in speaker_ids:
            id1 = str(speaker_id)

            a = id1.find("lvt_")
            b = id1.rfind("_")
            id2 = id1[a + 4 : b] if a >= 0 and b > a + 4 else None

            for speaker in all_speakers:
                if speaker not in parsed_speakers:
                    if (
                        speaker.device is not None
                        and (
                            speaker.device.id == str(id1)
                            or speaker.device.area_id == id1
                        )
                        or speaker.id == id1
                        or speaker.id == id2
                    ):
                        parsed_speakers.append(speaker)
        return parsed_speakers

    # endregion

    # region parse intents ######################################################
    def __parse_intent(self, parent, icfg):
        if not isinstance(icfg, dict):
            self.logError("LFT config: %s: Invalid intent definition", parent)

        for key in icfg:
            if key not in ["intent", "speaker", "utterance", "data"]:
                self.logError('LVT config: %s: Unknown property "%s" ', parent, key)
                return None

        if "intent" not in icfg:
            self.logError('LVT config: %s: "intent:" property not defined ', parent)
            return None

        utterance = None

        if "utterance" in icfg:
            utterance = []
            if isinstance(icfg["utterance"], str):
                utterance.append(icfg["utterance"])

            elif isinstance(icfg["utterance"], list):
                for u in icfg["utterance"]:
                    utterance.append(str(u))
            if len(utterance) == 0:
                self.logError(
                    'LVT config: %s: "utterance" should be the (list of) phases',
                    parent,
                )
                return None
        else:
            self.logError('LVT config: %s: "utterance" not defined', parent)
            return None

        if "speaker" in icfg:
            speaker = self.parse_speakers(icfg["speaker"], active_only=False)
        else:
            speaker = None

        if "data" in icfg:
            if isinstance(icfg["data"], dict) or isinstance(icfg["data"], OrderedDict):
                data = dict(icfg["data"])
            else:
                self.logError('LVT config: %s: "data" should be the dictionary', parent)
                return None
        else:
            data = None

        return {
            "Intent": str(icfg["intent"]),
            "Speaker": speaker,
            "Utterance": utterance,
            "Data": data,
        }

        return True

    def parse_intents(self, config) -> bool:
        if not isinstance(config, dict):
            self.logError("Invalid configuration file passed")
            return False
        errors = 0
        intents = []
        for key, cfg in config.items():
            if str(key).lower().startswith("intents"):
                if isinstance(cfg, list):
                    for i in range(len(cfg)):
                        intnt = self.__parse_intent(f"lvt => {key}[{i}]", cfg[i])
                        if intnt is not None:
                            intents.append(intnt)
                        else:
                            errors += 1
                else:
                    self.logError(
                        'LVT Config parser: Section "%s" should have list of intents',
                        key,
                    )
        if bool(intents) or bool(errors):
            self.__intents = intents
        return True

    # endregion

    # region get_call_XXXX() ####################################################
    def get_call_importance(self, call):
        """Retrieve call importance from LVT service call"""
        i = int(list(str(str(call.data.get("importance", 0)) + ":").partition(":"))[0])
        return 0 if i < 0 else 3 if i > 3 else i

    def get_call_speakers(self, call):
        """Retrieve list of speaker IDs for LVT call respecting importance and speaker status"""
        importance = self.get_call_importance(call)
        # Collect IDs all "enabled" speakers:
        speakers = self.parse_speakers(call.data.get("speaker", None), True)
        return [speaker.id for speaker in speakers if importance >= speaker.filter]

    # endregion

    # region handle_play ########################################################
    async def handle_play(self, call):
        """Handle "play" service call"""
        if not self.online:
            return
        sound = str(call.data.get("sound", ""))
        importance = self.get_call_importance(call)
        speakers = self.get_call_speakers(call)

        if not bool(sound):
            self.logError("lvt.play: <sound> parameter is empty")
            return
        if not bool(speakers):
            self.logInfo("lvt.play: no sutable speakers found")
            return

        self.synchronize_speakers()

        data = {"Sound": sound, "Importance": importance, "Terminals": speakers}
        self.send_message(MSG_API_PLAY, data=data)

    # endregion

    # region handle_say #########################################################
    async def handle_say(self, call):
        """Handle "say" service call."""
        if not self.online:
            return
        text = call.data.get("say", "")
        importance = self.get_call_importance(call)
        speakers = self.get_call_speakers(call)

        if not bool(text):
            self.logError("lvt.say: <say> parameter is empty")
            return

        if not bool(speakers):
            self.logInfo("lvt.say: no sutable speakers found")
            return

        self.synchronize_speakers()

        data = {"Say": text, "Importance": importance, "Terminals": speakers}
        self.send_message(MSG_API_SAY, data=data)

    # endregion

    # region handle_confirm #####################################################
    async def handle_confirm(self, call):
        """Handle "confirm" service call."""
        if not self.online:
            return
        say = call.data.get("say", None)
        importance = self.get_call_importance(call)
        speakers = self.get_call_speakers(call)

        if not bool(speakers):
            self.logInfo("lvt.confirm: no sutable speakers found")
            return

        self.synchronize_speakers()

        options = []
        options.append(
            {
                "Intent": call.data.get("no_intent", None),
                "Say": call.data.get("no_say", None),
                "Utterance": [
                    "Нет",
                    "Отмена",
                    "Стой",
                    "Отказ",
                    "Не согласен",
                    "Ни в коем случае",
                ],
                "Data": call.data.get("no_data", {}),
            }
        )
        options.append(
            {
                "Intent": call.data.get("yes_intent", None),
                "Say": call.data.get("yes_say", None),
                "Utterance": [
                    "Да",
                    "Согласен",
                    "Хорошо",
                    "Конечно да",
                    "Конечно",
                    "Продолжай",
                    "Безусловно",
                ],
                "Data": call.data.get("yes_data", {}),
            }
        )

        data = {
            "Say": say,
            "Importance": importance,
            "Terminals": speakers,
            "Prompt": call.data.get("prompt", None),
            "Options": options,
            "DefaultSay": call.data.get("default_say", None),
            "DefaultIntent": call.data.get("default_intent", None),
            "DefaultTimeout": call.data.get("default_timeout", None),
            "DefaultData": call.data.get("default_data", None),
        }
        self.send_message(MSG_API_NEGOTIATE, data=data)

    # endregion

    # region handle_negotiate ###################################################
    async def handle_negotiate(self, call):
        """Handle "say" service call."""
        if not self.online:
            return
        say = call.data.get("say", None)
        importance = self.get_call_importance(call)
        speakers = self.get_call_speakers(call)

        if not bool(speakers):
            self.logInfo("lvt.negotiate: no sutable speakers found")
            return

        self.synchronize_speakers()

        index = []
        options = []
        for name, value in call.data.items():
            n = str(name).split("_")
            if n[0] == "option":
                if len(n) == 3 and int(n[1]) > 0 and int(n[1]) < 11:
                    if int(n[1]) not in index:
                        index.append(int(n[1]))
                else:
                    self.logError("Invalid LVT negotiate option parameter: %s", name)
        index.sort()
        for o in index:
            options.append({"Intent": None, "Utterance": None, "Say": None})
        for name, value in call.data.items():
            n = str(name).split("_")
            if n[0] == "option":
                if int(n[1]) in index:
                    o = index.index(int(n[1]))
                    if n[2] == "intent":
                        options[o]["Intent"] = value
                    elif n[2] == "utterance":
                        options[o]["Utterance"] = value
                    elif n[2] == "say":
                        options[o]["Say"] = value
                    elif n[2] == "data":
                        options[o]["Data"] = value
                    else:
                        self.logError("Invalid LVT negotiate option: %s", name)
                else:
                    self.logError("Invalid LVT negotiate option parameter: %s", name)

        data = {
            "Say": say,
            "Importance": importance,
            "Terminals": speakers,
            "Prompt": call.data.get("prompt", None),
            "Options": options,
            "DefaultSay": call.data.get("default_say", None),
            "DefaultIntent": call.data.get("default_intent", None),
            "DefaultTimeout": call.data.get("default_timeout", None),
            "DefaultData": call.data.get("default_data", None),
        }
        self.send_message(MSG_API_NEGOTIATE, data=data)

    # endregion

    # region logInfo / logDebug / logWarning / logError #########################
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


# region async_server_test() ####################################################
async def async_server_test(
    hass: HomeAssistantType, server: str, port: int, password: str, ssl_mode: int
) -> bool:
    """Test if we can LVT API Server is available"""
    _ok = False

    try:
        session = async_get_clientsession(hass)

        async with session.ws_connect(
            f"{get_protocol(ssl_mode)}://{server}:{port}/api",
            ssl=get_ssl_context(ssl_mode),
        ) as ws:
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
        pass

    return _ok


# endregion
