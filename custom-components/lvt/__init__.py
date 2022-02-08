"""The Lite Voice Terminal integration"""
from __future__ import annotations
from .lvt import LvtApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN, CONFIG_TYPE_YAML, CONFIG_TYPE_ENTRY, LVT_PLATFORMS


async def async_initialize(hass: HomeAssistant, config_type: int, config: dict) -> bool:
    if DOMAIN in hass.data:
        lvt: LvtApi = hass.data[DOMAIN]
        lvt.configure(
            config["server"] if "server" in config else None,
            config["port"] if "port" in config else None,
            config["password"] if "password" in config else None,
        )
    else:
        hass.data[DOMAIN] = lvt = LvtApi(
            hass,
            config["server"] if "server" in config else None,
            config["port"] if "port" in config else None,
            config["password"] if "password" in config else None,
        )

    lvt.config_type = config_type

    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Lite Voice Terminal using configuration in yaml"""
    if config is None:
        return False
    if DOMAIN not in config:
        return True

    _ok = await async_initialize(hass, CONFIG_TYPE_YAML, config[DOMAIN])
    if _ok:
        for platform in LVT_PLATFORMS:
            hass.async_create_task(
                async_load_platform(hass, platform, DOMAIN, {}, config[DOMAIN])
            )
    return _ok


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Lite Voice Terminal using a config entry (with UI)"""
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))
    _ok = await async_initialize(
        hass, CONFIG_TYPE_ENTRY, {**config_entry.data, **config_entry.options}
    )

    if _ok:
        for platform in LVT_PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
            )
    return _ok


async def async_update_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Re-configure Lite Voice Terminal using a config entry (with UI)"""
    return await async_initialize(
        hass, CONFIG_TYPE_ENTRY, {**config_entry.data, **config_entry.options}
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, LVT_PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].stop()
        hass.data.pop(DOMAIN)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload LVT config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
