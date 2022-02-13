"""The Lite Voice Terminal integration"""
from __future__ import annotations
from .lvt import LvtApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN, LVT_PLATFORMS, ssl_mode_to_int


async def async_initialize(hass: HomeAssistant, config) -> bool:
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = LvtApi(hass)

    lvt: LvtApi = hass.data[DOMAIN]

    # if lvt intents are in config:
    #     lvt.configure_intents
    #

    if "server" in config and "password" in config:
        lvt.configure_connection(
            config["server"],
            config["port"] if "port" in config else None,
            config["password"],
            ssl_mode_to_int(config["ssl"] if "ssl" in config else 0),
        )

    return True


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Set up Lite Voice Terminal using configuration in yaml"""
    if config is None:
        return False
    if DOMAIN not in config:
        return True
    _ok = await async_initialize(hass, config[DOMAIN])
    if _ok:
        for platform in LVT_PLATFORMS:
            hass.async_create_task(
                async_load_platform(hass, platform, DOMAIN, {}, config[DOMAIN])
            )
    return _ok


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Lite Voice Terminal using a config entry (with UI)"""
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    _ok = await async_initialize(hass, {**config_entry.data, **config_entry.options})

    if _ok:
        for platform in LVT_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )
    return _ok


async def async_update_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Re-configure Lite Voice Terminal using a config entry (with UI)"""
    return await async_initialize(hass, {**config_entry.data, **config_entry.options})


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, LVT_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].stop()
        del hass.data[DOMAIN]
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload LVT config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
