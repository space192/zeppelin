from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import BwZeppelinApiClient, BwZeppelinApiError
from .const import CONF_FW_VERSION, CONF_MODEL, CONF_NODE_ID, CONF_SPACE_NAME, DOMAIN
from .light import DEVICE_TYPE_NAMES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BwZeppelinUpdate(data["api"], entry)])


class BwZeppelinUpdate(UpdateEntity):

    _attr_has_entity_name = True
    _attr_name = "Firmware"
    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(self, api: BwZeppelinApiClient, entry: ConfigEntry) -> None:
        self._api = api
        self._installed_version = entry.data.get(CONF_FW_VERSION, "unknown")
        self._latest_version: str | None = None
        self._release_notes: str = ""

        node_id = entry.data[CONF_NODE_ID]
        self._attr_unique_id = f"{node_id}_firmware"
        model_type = entry.data.get(CONF_MODEL, "unknown")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, node_id)},
            "name": entry.data.get(CONF_SPACE_NAME, "Zeppelin"),
            "manufacturer": "Bowers & Wilkins",
            "model": DEVICE_TYPE_NAMES.get(model_type, model_type),
            "sw_version": entry.data.get(CONF_FW_VERSION),
        }

    @property
    def installed_version(self) -> str:
        return self._installed_version

    @property
    def latest_version(self) -> str | None:
        return self._latest_version or self._installed_version

    async def async_update(self) -> None:
        try:
            result = await self._api.check_software_update()
        except BwZeppelinApiError:
            _LOGGER.debug("Failed to check for firmware update")
            return
        if result.get("update_available"):
            self._latest_version = result.get("update_version")
            self._release_notes = result.get("update_release_notes", "")
        else:
            self._latest_version = self._installed_version
            self._release_notes = ""

    async def async_release_notes(self) -> str | None:
        return self._release_notes or None

    async def async_install(self, version: str | None, backup: bool, **kwargs: Any) -> None:
        try:
            await self._api.start_software_update()
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to start firmware update")
