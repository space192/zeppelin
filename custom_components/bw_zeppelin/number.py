from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import BwZeppelinApiClient, BwZeppelinApiError
from .const import CONF_FW_VERSION, CONF_MODEL, CONF_NODE_ID, CONF_SPACE_NAME, DEFAULT_AUDIO_OUTPUT_DELAY_US, DOMAIN, PROPERTY_GAIN_BASS, PROPERTY_GAIN_TREBLE
from .light import DEVICE_TYPE_NAMES

_LOGGER = logging.getLogger(__name__)

EQ_CONTROLS = [
    {"name": "Bass", "property": PROPERTY_GAIN_BASS, "icon": "mdi:speaker"},
    {"name": "Treble", "property": PROPERTY_GAIN_TREBLE, "icon": "mdi:music-clef-treble"},
]

# Audio output delay exposed in milliseconds for readability; the speaker API
# uses microseconds. Negative values pull the speaker back into sync in
# AirPlay 2 groups (see README).
AUDIO_OUTPUT_DELAY_MIN_MS = -1000
AUDIO_OUTPUT_DELAY_MAX_MS = 1000
AUDIO_OUTPUT_DELAY_STEP_MS = 10


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    initial_eq = data.get("initial_eq", {})
    entities = []
    for ctrl in EQ_CONTROLS:
        raw = initial_eq.get(ctrl["property"], 0)
        entities.append(BwZeppelinEQ(api, entry, ctrl, raw))

    initial_delay_us = data.get("initial_audio_output_delay", DEFAULT_AUDIO_OUTPUT_DELAY_US)
    entities.append(BwZeppelinAudioOutputDelay(api, entry, initial_delay_us))
    async_add_entities(entities)


class BwZeppelinEQ(NumberEntity):

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = -6.0
    _attr_native_max_value = 6.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        api: BwZeppelinApiClient,
        entry: ConfigEntry,
        ctrl: dict,
        initial_raw: int,
    ) -> None:
        self._api = api
        self._property = ctrl["property"]
        self._attr_name = ctrl["name"]
        self._attr_icon = ctrl["icon"]
        self._raw_value = initial_raw

        node_id = entry.data[CONF_NODE_ID]
        slug = ctrl["name"].lower()
        self._attr_unique_id = f"{node_id}_{slug}"
        model_type = entry.data.get(CONF_MODEL, "unknown")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, node_id)},
            "name": entry.data.get(CONF_SPACE_NAME, "Zeppelin"),
            "manufacturer": "Bowers & Wilkins",
            "model": DEVICE_TYPE_NAMES.get(model_type, model_type),
            "sw_version": entry.data.get(CONF_FW_VERSION),
        }

    @property
    def native_value(self) -> float:
        return self._raw_value / 100.0

    async def async_set_native_value(self, value: float) -> None:
        raw = int(round(value)) * 100
        try:
            await self._api.set_eq(self._property, raw)
            self._raw_value = raw
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to set %s", self._attr_name)
            return
        self.async_write_ha_state()


class BwZeppelinAudioOutputDelay(NumberEntity):

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = AUDIO_OUTPUT_DELAY_MIN_MS
    _attr_native_max_value = AUDIO_OUTPUT_DELAY_MAX_MS
    _attr_native_step = AUDIO_OUTPUT_DELAY_STEP_MS
    _attr_native_unit_of_measurement = "ms"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:timer-sync-outline"

    def __init__(
        self,
        api: BwZeppelinApiClient,
        entry: ConfigEntry,
        initial_delay_us: int,
    ) -> None:
        self._api = api
        self._delay_us = initial_delay_us

        node_id = entry.data[CONF_NODE_ID]
        self._attr_name = "Audio Output Delay"
        self._attr_unique_id = f"{node_id}_audio_output_delay"
        model_type = entry.data.get(CONF_MODEL, "unknown")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, node_id)},
            "name": entry.data.get(CONF_SPACE_NAME, "Zeppelin"),
            "manufacturer": "Bowers & Wilkins",
            "model": DEVICE_TYPE_NAMES.get(model_type, model_type),
            "sw_version": entry.data.get(CONF_FW_VERSION),
        }

    @property
    def native_value(self) -> float:
        return round(self._delay_us / 1000.0, 1)

    async def async_set_native_value(self, value: float) -> None:
        microseconds = int(round(value)) * 1000
        try:
            await self._api.set_audio_output_delay(microseconds)
            self._delay_us = microseconds
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to set %s", self._attr_name)
            return
        self.async_write_ha_state()
