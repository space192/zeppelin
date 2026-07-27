from __future__ import annotations

import logging
import random

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change

from .api_client import BwZeppelinApiClient, BwZeppelinApiError
from .const import CONF_HOST, CONF_NODE_ID, CONF_SPACE_NAME, DOMAIN, PROPERTY_GAIN_BASS, PROPERTY_GAIN_TREBLE
from .ws_client import BwZeppelinWebSocket

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.LIGHT, Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=False)
    host = entry.data[CONF_HOST]
    api = BwZeppelinApiClient(
        session=session,
        host=host,
        node_id=entry.data[CONF_NODE_ID],
    )

    initial_light_state = await api.get_light_state()

    try:
        device_info = await api.get_device_info()
    except BwZeppelinApiError:
        _LOGGER.warning("Failed to fetch device info for diagnostics")
        device_info = {}

    initial_eq = {}
    for prop in (PROPERTY_GAIN_BASS, PROPERTY_GAIN_TREBLE):
        try:
            initial_eq[prop] = await api.get_eq(prop)
        except BwZeppelinApiError:
            _LOGGER.warning("Failed to fetch initial EQ value for %s", prop)

    ws_client = BwZeppelinWebSocket(host)
    ws_client.start(hass)

    check_hour = random.randint(3, 5)
    check_minute = random.randint(0, 59)
    space_name = entry.data.get(CONF_SPACE_NAME, "Zeppelin")
    _LOGGER.info(
        "Scheduling firmware update check for %s at %02d:%02d",
        space_name, check_hour, check_minute,
    )

    async def _check_firmware_update(_now) -> None:
        try:
            result = await api.check_software_update()
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to check for firmware update")
            return

        if result.get("update_available"):
            version = result.get("update_version", "unknown")
            notes = result.get("update_release_notes", "")
            message = f"Firmware **{version}** is available for your {space_name}."
            if notes:
                message += f"\n\n{notes}"
            await hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": f"B&W {space_name} — Firmware Update",
                    "message": message,
                    "notification_id": f"{DOMAIN}_update_{entry.entry_id}",
                },
            )

    unsub = async_track_time_change(
        hass, _check_firmware_update, hour=check_hour, minute=check_minute, second=0
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "ws_client": ws_client,
        "initial_light_state": initial_light_state,
        "device_info": device_info,
        "initial_eq": initial_eq,
        "unsub_update_check": unsub,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        data["ws_client"].stop()
        data["unsub_update_check"]()
    return unload_ok
