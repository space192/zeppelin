from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import BwZeppelinApiClient, BwZeppelinApiError
from .const import CMD_NEXT, CMD_PLAY_PAUSE, CMD_PREVIOUS, CONF_FW_VERSION, CONF_MODEL, CONF_NODE_ID, CONF_SPACE_NAME, DOMAIN
from .light import DEVICE_TYPE_NAMES
from .ws_client import BwZeppelinWebSocket

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BwZeppelinMediaPlayer(data["api"], data["ws_client"], entry)])


class BwZeppelinMediaPlayer(MediaPlayerEntity):

    _attr_has_entity_name = True
    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(
        self,
        api: BwZeppelinApiClient,
        ws_client: BwZeppelinWebSocket,
        entry: ConfigEntry,
    ) -> None:
        self._api = api
        self._ws_client = ws_client
        self._unsub_ws: Any = None

        self._tile: dict = {}

        node_id = entry.data[CONF_NODE_ID]
        self._attr_unique_id = f"{node_id}_media_player"
        model_type = entry.data.get(CONF_MODEL, "unknown")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, node_id)},
            "name": entry.data.get(CONF_SPACE_NAME, "Zeppelin"),
            "manufacturer": "Bowers & Wilkins",
            "model": DEVICE_TYPE_NAMES.get(model_type, model_type),
            "sw_version": entry.data.get(CONF_FW_VERSION),
        }

    async def async_added_to_hass(self) -> None:
        self._unsub_ws = self._ws_client.register_audiotile_callback(self._on_audiotile)

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_ws:
            self._unsub_ws()

    @callback
    def _on_audiotile(self, tile: dict) -> None:
        self._tile = tile
        self._attr_media_position_updated_at = dt.datetime.now(dt.timezone.utc)
        self.async_write_ha_state()

    @property
    def state(self) -> MediaPlayerState:
        if not self._tile:
            return MediaPlayerState.IDLE
        if self._tile.get("state") == 1:
            return MediaPlayerState.PLAYING
        if self._tile.get("title"):
            return MediaPlayerState.PAUSED
        return MediaPlayerState.IDLE

    @property
    def media_title(self) -> str | None:
        return self._tile.get("title") or None

    @property
    def media_artist(self) -> str | None:
        return self._tile.get("artist") or None

    @property
    def media_album_name(self) -> str | None:
        return self._tile.get("album") or None

    @property
    def media_duration(self) -> float | None:
        duration = self._tile.get("duration")
        if duration is not None:
            return duration / 1000.0
        return None

    @property
    def media_position(self) -> float | None:
        elapsed = self._tile.get("elapsedTime")
        if elapsed is not None:
            return elapsed / 1000.0
        return None

    @property
    def source(self) -> str | None:
        return self._tile.get("serviceName") or None

    async def async_media_play(self) -> None:
        try:
            await self._api.send_command(CMD_PLAY_PAUSE)
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to send play command")

    async def async_media_pause(self) -> None:
        try:
            await self._api.send_command(CMD_PLAY_PAUSE)
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to send pause command")

    async def async_media_next_track(self) -> None:
        try:
            await self._api.send_command(CMD_NEXT)
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to send next track command")

    async def async_media_previous_track(self) -> None:
        try:
            await self._api.send_command(CMD_PREVIOUS)
        except BwZeppelinApiError:
            _LOGGER.exception("Failed to send previous track command")
