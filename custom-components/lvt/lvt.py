"""LVT API"""
import asyncio
import json
import logging
import random
import ssl
import time

import aiohttp
from homeassistant.core import HassJob

from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import intent
from .const import (
    DOMAIN,
    LVT_PLATFORMS,
    MSG_API_AUTHORIZE,
    MSG_API_ERROR,
    MSG_API_FIRE_INTENT,
    MSG_API_NEGOTIATE,
    MSG_API_LISTENING_START,
    MSG_API_LISTENING_STOP,
    MSG_API_PLAY,
    MSG_API_RESTART,
    MSG_API_SAY,
    MSG_API_SERVER_STATUS,
    MSG_API_SET_INTENTS,
    MSG_API_SPEAKER_STATUS,
)
from .lvt_speaker import LvtSpeaker

_LOGGER = logging.getLogger(__name__)

# region get_protocol / get_ssl_context #########################################
def get_protocol(ssl_mode: int) -> str:
    """HTTPS or HTTP"""
    return "https" if ssl_mode > 0 else "http"


def get_ssl_context(ssl_mode: int):
    """Create and initialize SSLContext if required"""
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
        hass.services.async_register(
            DOMAIN, "listening_start", self.handle_listening_start
        )
        hass.services.async_register(
            DOMAIN, "listening_stop", self.handle_listening_stop
        )
        hass.services.async_register(DOMAIN, "restart_speaker", self.handle_restart)
        self.__loaded_platforms = set()

    def __del__(self):
        """Destructor (just in case)"""
        self.stop()
        self.hass.services.async_remove(DOMAIN, "play")
        self.hass.services.async_remove(DOMAIN, "say")
        self.hass.services.async_remove(DOMAIN, "confirm")
        self.hass.services.async_remove(DOMAIN, "negotiate")
        self.hass.services.async_remove(DOMAIN, "listening_start")
        self.hass.services.async_remove(DOMAIN, "listening_stop")
        self.hass.services.async_remove(DOMAIN, "restart_speaker")

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
        """process and check intents passed"""
        if self.online:
            pass

    def platform_loaded(self, platform):
        """Register platform as loaded"""
        self.__loaded_platforms.add(platform)

    def add_trigger(self, config, action, automation):
        """Register trigger to track"""
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
    def intents(self) -> list:
        """self.intents"""
        return self.__intents

    @property
    def started(self) -> bool:
        """If WS client started"""
        return self.__client_task is not None

    @property
    def online(self) -> bool:
        """Online status"""
        return self.__online

    @property
    def platforms_loaded(self) -> bool:
        """If all platforms loaded"""
        return set(self.__loaded_platforms) == set(LVT_PLATFORMS)

    @online.setter
    def online(self, is_online: bool):
        """Update .online property and "lvt.online" entity"""
        if is_online != self.__online:
            self.log_debug(
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
        """If WS client is connected and atuthorized on LVT server"""
        return self.__authorized

    # endregion

    # region WebSock client implementation: start / stop / send_message #########
    def start(self):
        """Start LVT API Client task"""
        if not self.started:
            self.__wstask_id = str(random.randrange(100, 999))
            self.log_debug("Starting websock client")

            self.__online = False
            self.__client_task = asyncio.create_task(self.__websock_client())

    def stop(self):
        """Stop LVT API Client task"""
        if self.started:
            self.log_debug("Stopping websock client")
            self.__client_task.cancel()
            self.__client_task = None

    def send_message(
        self,
        msg: str,
        status_code: int = 0,
        status: str = None,
        data=None,
    ):
        """Queue message to LVT server"""
        message = {"Message": msg, "StatusCode": status_code}
        if status is not None:
            message["Status"] = str(status)
        if data is not None:
            message["Data"] = json.dumps(data)

        self.__queue.append(message)

    def synchronize_speakers(self):
        """Send speaker state changes to LVT server"""
        self.__speakers_synced = time.time()
        data = {}
        for _, speaker in self.speakers.items():
            if speaker.out_of_sync:
                data[speaker.id] = {"Volume": speaker.volume, "Filter": speaker.filter}
        if data:
            self.send_message(MSG_API_SPEAKER_STATUS, data=data)

    def send_intents(self):
        """Send active intents configuration to LVT server"""
        self.send_message(MSG_API_SET_INTENTS, data=self.intents)

    # endregion

    # region __websock_client() #################################################
    async def __websock_client(self):
        self.log_debug(
            "Waiting for configuration and loading platforms: %s", LVT_PLATFORMS
        )
        session_started = time.time()
        error_reported = False
        while True:
            if (
                not self.platforms_loaded
                or not bool(self.__server)
                or not bool(self.__port)
                or not bool(self.__password)
            ):
                if ((time.time() - session_started) > 30) and not error_reported:
                    error_reported = True
                    if not self.platforms_loaded:
                        self.log_error("Not all LVT platforms loaded!")
                    else:
                        self.log_error(
                            "Missing Lite Voice Terminal connection config. Please consult LVT documentation"
                        )
                await asyncio.sleep(1)
                continue
            else:
                error_reported = False

            self.online = False
            try:
                url = f"{get_protocol(self.ssl_mode)}://{self.server}:{self.port}/api"
                self.log_debug("Connecting %s", url)
                self.__speakers_synced = time.time()
                async with async_get_clientsession(self.hass).ws_connect(
                    url, heartbeat=10, ssl=get_ssl_context(self.ssl_mode)
                ) as ws:
                    self.__ws = ws
                    session_started = time.time()
                    self.online = True
                    if self.password is not None:
                        self.send_message(MSG_API_AUTHORIZE, data=str(self.password))
                    while True:
                        # Check if not authorized within 5 seconds
                        if not self.authorized and (
                            (time.time() - session_started) > 5
                        ):
                            self.log_error("Not authorized!")
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

                        # region ожидание сообщения ##########
                        try:
                            msg = await ws.receive(0.5)
                            if msg is None:
                                continue
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
                                    continue
                            elif msg.type == aiohttp.WSMsgType.CLOSED:
                                break
                            else:
                                continue
                        except asyncio.TimeoutError:
                            continue
                        # endregion

                        # Process message received
                        if msg == MSG_API_AUTHORIZE:  # LVT Server status message
                            if status_code == 0:
                                self.log_debug("Authorized")
                                self.__authorized = True
                                self.send_intents()
                            else:
                                self.log_error(
                                    "Authnentication failure: Invalid password."
                                )
                                await ws.close()

                        if msg == MSG_API_SERVER_STATUS:  # LVT Server status message
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
                                self.log_error(
                                    "LVT API.FireIntent: Intent not specified "
                                )
                            intent_type = data["Intent"]
                            intent_data = data["Data"] if "Data" in data else {}
                            intent_data["intent"] = intent_type

                            intent_importance = (
                                data["Importance"] if "Importance" in data else 1
                            )
                            intent_speaker = (
                                data["Terminal"] if "Terminal" in data else None
                            )

                            # region Fire An Intent
                            slots = {
                                key: {"value": value}
                                for key, value in intent_data.items()
                            }
                            try:
                                response = await intent.async_handle(
                                    self.hass, DOMAIN, intent_type, slots
                                )
                                self.log(str(response))

                                if "plain" in response.speech:
                                    self.send_message(
                                        MSG_API_SAY,
                                        data={
                                            "Say": response.speech["plain"]["speech"],
                                            "Importance": intent_importance,
                                            "Terminals": [intent_speaker],
                                        },
                                    )

                            except intent.UnknownIntent:
                                self.log_warning(
                                    "Received unknown intent %s", intent_type
                                )

                            except intent.InvalidSlotInfo as err:
                                self.log_error(
                                    "Received invalid slot data for intent %s: %s",
                                    intent_type,
                                    err,
                                )

                            except intent.IntentError as e:
                                self.log_error(
                                    "Handling request for %s: %s %s",
                                    intent_type,
                                    type(e).__name__,
                                    e,
                                )
                            # endregion

                            # region Trigger Triggers
                            for trigger in self.__triggers:
                                cfg = trigger["config"]
                                t_intent = (
                                    str(cfg["intent"]) if "intent" in cfg else None
                                )
                                if t_intent.lower() == intent_type.lower():
                                    job = HassJob(trigger["action"])
                                    trigger_data = trigger["automation"]["trigger_data"]

                                    self.hass.async_run_hass_job(
                                        job,
                                        {
                                            "trigger": {
                                                **trigger_data,
                                                "platform": DOMAIN,
                                                "intent": intent_type,
                                                "data": intent_data,
                                                "description": f'Intent "{intent_type}" fired by "{intent_speaker}"',
                                            }
                                        },
                                        None,
                                    )
                            # endregion
                        elif msg == MSG_API_ERROR:
                            self.log_error(
                                "LVT Server error #%s: %s",
                                str(status_code),
                                str(status),
                            )

            except aiohttp.ClientConnectionError as e:
                self.log_warning("Error connecting server: %s", str(e))
                await asyncio.sleep(5)
            except Exception as ex:
                self.log_error("API error [%s]: %s", type(e).__name__, str(ex))
                await asyncio.sleep(5)
            except:
                self.log_debug("API client stopped")
                break
            finally:
                self.online = False

    # endregion

    # region speaker manipulation: update, delete, create etc ###################

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
            self.log_error(
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
        """Create entities for speakers registered earlier"""
        ids = []
        registry = self.hass.data["device_registry"]
        if registry is not None:
            for _, device in registry.devices.items():
                try:
                    l = list(device.identifiers)[0]
                    if len(l) > 1:
                        domain, speaker_id = l
                        if domain == DOMAIN and (speaker_id not in self.speakers):
                            self.speakers[speaker_id] = LvtSpeaker(
                                self.hass, speaker_id, self.online
                            )
                except Exception:
                    pass
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
        elif isinstance(speakers, list):
            speaker_ids = [str(speaker) for speaker in speakers]
        else:
            speaker_ids = [str(speakers)]

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
            self.log_error("LVT config: %s: Invalid intent definition", parent)

        for key in icfg:
            if key not in ["intent", "speaker", "utterance"]:
                self.log_error('LVT config: %s: Unknown property "%s" ', parent, key)
                return None

        if "intent" not in icfg:
            self.log_error('LVT config: %s: "intent:" property not defined ', parent)
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
                self.log_error(
                    'LVT config: %s: "utterance" should be the (list of) phases',
                    parent,
                )
                return None
        else:
            self.log_error('LVT config: %s: "utterance" not defined', parent)
            return None

        if "speaker" in icfg:
            speakers = icfg["speaker"]
            if isinstance(speakers, dict):
                speakers = [str(speaker).lower() for speaker in speakers.keys()]
            elif isinstance(speakers, list):
                speakers = [str(speaker).lower() for speaker in speakers]
            else:
                speakers = [str(speakers).lower()]
        else:
            speakers = []

        return {
            "Intent": str(icfg["intent"]),
            "Terminals": speakers,
            "Utterance": utterance,
        }

    def parse_intents(self, config) -> bool:
        """Parse intent definition from YAML config"""
        if not isinstance(config, dict):
            self.log_error("Invalid configuration file passed")
            return False
        errors = 0
        # intents = []
        for key, cfg in config.items():
            if str(key).lower().startswith("intents"):
                if isinstance(cfg, list):
                    for i in range(len(cfg)):
                        intnt = self.__parse_intent(f"lvt => {key}[{i}]", cfg[i])
                        if intnt is not None:
                            self.__intents.append(intnt)
                        else:
                            errors += 1
                else:
                    self.log_error(
                        'LVT Config parser: Section "%s" should have list of intents',
                        key,
                    )
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
        sound = str(call.data.get("play", ""))
        importance = self.get_call_importance(call)
        speakers = self.get_call_speakers(call)

        if not bool(sound):
            self.log_error("lvt.play: <play> parameter is empty")
            return
        if not bool(speakers):
            self.log("lvt.play: no sutable speakers found")
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
            self.log_error("lvt.say: <say> parameter is empty")
            return

        if not bool(speakers):
            self.log("lvt.say: no sutable speakers found")
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
            self.log("lvt.confirm: no sutable speakers found")
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
            "DefaultUtterance": call.data.get("default_utterance", None),
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
            self.log("lvt.negotiate: no sutable speakers found")
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
                    self.log_error("Invalid LVT negotiate option parameter: %s", name)
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
                    else:
                        self.log_error("Invalid LVT negotiate option: %s", name)
                else:
                    self.log_error("Invalid LVT negotiate option parameter: %s", name)

        data = {
            "Say": say,
            "Importance": importance,
            "Terminals": speakers,
            "Prompt": call.data.get("prompt", None),
            "Options": options,
            "DefaultSay": call.data.get("default_say", None),
            "DefaultIntent": call.data.get("default_intent", None),
            "DefaultTimeout": call.data.get("default_timeout", None),
            "DefaultUtterance": call.data.get("default_utterance", None),
        }
        self.send_message(MSG_API_NEGOTIATE, data=data)

    # endregion

    # region handle_listening_start / handle_listening_stop #####################
    async def handle_listening_start(self, call):
        """Handle "listening_start" service call."""
        if not self.online:
            return
        speakers = self.get_call_speakers(call)
        importance = self.get_call_importance(call)
        if not bool(call.data.get("say", None)):
            self.log_error("lvt.listening_start: Параметр say не задан")
            return
        if not bool(call.data.get("prompt", None)):
            self.log_error("lvt.listening_start: Параметр prompt не задан")
            return
        if not bool(speakers):
            self.log("lvt.listening_start: Подходящие терминалы не найдены")
            return
        if not bool(call.data.get("intent", None)):
            self.log_error("lvt.listening_start: Параметр intent не задан")
            return

        self.synchronize_speakers()

        model = list(str(str(call.data.get("model", "f")) + ":").partition(":"))[0]

        data = {
            "Say": call.data.get("say", None),
            "Importance": importance,
            "Terminals": speakers,
            "Model": "d" if model == "d" else "f",
            "Prompt": call.data.get("prompt", None),
            "Intent": call.data.get("intent", None),
            "DefaultSay": call.data.get("default_say", None),
            "DefaultIntent": call.data.get("default_intent", None),
            "DefaultTimeout": call.data.get("default_timeout", None),
        }
        self.send_message(MSG_API_LISTENING_START, data=data)

    async def handle_listening_stop(self, call):
        """Handle "listening_stop" service call."""
        if not self.online:
            return
        speakers = self.parse_speakers(call.data.get("speaker", None), True)
        speakerIds = [speaker.id for speaker in speakers]

        if not bool(speakerIds):
            self.log("lvt.listening_stop: подходящие терминалы не найдены")
            return

        self.synchronize_speakers()
        say = call.data.get("say", None)
        data = {
            "Intent": call.data.get("intent", None),
            "Say": say,
            "Importance": 2,
            "Terminals": speakerIds,
        }
        self.send_message(MSG_API_LISTENING_STOP, data=data)

    # endregion

    # region handle_restart #####################################################
    async def handle_restart(self, call):
        """Handle "say" service call."""
        if not self.online:
            return
        speakers = self.parse_speakers(
            call.data.get("speaker", None), active_only=False
        )
        speakers = [speaker.id for speaker in speakers]
        update = bool(call.data.get("update", False))
        say = call.data.get("say", None)
        say_on_connect = call.data.get("say_on_restart", None)

        if not bool(speakers):
            self.log("lvt.restart: no sutable speakers found")
            return

        self.send_message(
            MSG_API_RESTART,
            data={
                "Terminals": speakers,
                "Update": update,
                "Say": say,
                "SayOnConnect": say_on_connect,
            },
        )

    # endregion

    # region log / log_debug / log_warning / log_error #########################
    def log(self, msg: str, *args, **kwargs):
        """Log informational message"""
        msg = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.info(msg, *args, **kwargs)

    def log_debug(self, msg: str, *args, **kwargs):
        """Log debug message"""
        msg = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.debug(msg, *args, **kwargs)

    def log_warning(self, msg: str, *args, **kwargs):
        """Log warning message"""
        msg = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.warning(msg, *args, **kwargs)

    def log_error(self, msg: str, *args, **kwargs):
        """Log error message"""
        msg = "{}@{} {}".format(self.__wstask_id, self._api_id, msg)
        _LOGGER.error(msg, *args, **kwargs)

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
